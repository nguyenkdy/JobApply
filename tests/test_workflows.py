import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import jwt
import pytest
from pypdf import PdfWriter
from sqlalchemy import func, select

from shared.runtime import now


def register(api, role="Candidate"):
    email = f"{uuid4().hex}@example.com"
    body = {"email": email, "password": "CorrectPassword123!", "full_name": "Test User", "role": role}
    response = api["account"].post("/auth/register", json=body)
    assert response.status_code == 201, response.text
    response = api["account"].post("/auth/login", json={"email": email, "password": body["password"]})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}, response.json()["user"], body


def company(api, headers):
    response = api["job"].post("/companies", headers=headers, json={"name": "Test Company", "location": "Hà Nội"})
    assert response.status_code == 201, response.text
    return response.json()


def job(api, headers, publish=True):
    response = api["job"].post(
        "/jobs",
        headers=headers,
        json={
            "title": "Python Developer",
            "description": "Build Python services for customers",
            "requirements": "Python and SQL experience",
            "location": "Hà Nội",
            "level": "Junior",
            "work_mode": "Hybrid",
            "salary": "20 triệu",
            "deadline": (now() + timedelta(days=5)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    if publish:
        assert (
            api["job"].patch(f"/jobs/{data['id']}/status", headers=headers, json={"status": "Published"}).status_code
            == 200
        )
    return data


def pdf(title="Version one"):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": title})
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def upload(api, headers, title="Version one"):
    response = api["account"].post(
        "/cvs", headers=headers, data={"name": title}, files={"file": ("../../cv.pdf", pdf(title), "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def flow(api):
    recruiter, _, _ = register(api, "Recruiter")
    candidate, candidate_user, _ = register(api)
    comp = company(api, recruiter)
    vacancy = job(api, recruiter)
    cv = upload(api, candidate)
    return {
        "recruiter": recruiter,
        "candidate": candidate,
        "candidate_user": candidate_user,
        "company": comp,
        "job": vacancy,
        "cv": cv,
    }


def submit(api, flow, **overrides):
    return api["application"].post(
        "/applications",
        headers=flow["candidate"],
        json={"job_id": flow["job"]["id"], "cv_id": flow["cv"]["id"], "introduction": "Hello team", **overrides},
    )


def test_register_login_and_invalid_tokens(api):
    headers, user, body = register(api)
    assert api["account"].get("/me", headers=headers).json()["id"] == user["id"]
    assert api["account"].post("/auth/register", json=body).status_code == 409
    assert api["account"].post("/auth/login", json={"email": body["email"], "password": "wrong"}).status_code == 401
    assert api["account"].get("/me", headers={"X-User-Id": user["id"], "X-Role": "Candidate"}).status_code == 401
    assert api["account"].get("/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    claims = {
        "sub": user["id"],
        "role": "Candidate",
        "iss": "jobapply-account",
        "aud": "jobapply",
        "iat": now() - timedelta(hours=2),
        "exp": now() - timedelta(hours=1),
    }
    for mutation in (
        {},
        {"aud": "wrong", "exp": now() + timedelta(hours=1)},
        {"role": "Admin", "exp": now() + timedelta(hours=1)},
    ):
        token = jwt.encode({**claims, **mutation}, os.environ["JWT_SECRET"], algorithm="HS256")
        assert api["account"].get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    token = headers["Authorization"].split()[1]
    assert api["account"].get("/me", headers={"Authorization": f"Bearer {token[:-8]}forgedxx"}).status_code == 401


def test_end_to_end_and_immutable_snapshot(api, flow):
    found = api["job"].get("/jobs?q=Python&location=Hà Nội&level=Junior&work_mode=Hybrid&limit=100").json()
    assert any(item["id"] == flow["job"]["id"] for item in found)
    response = submit(api, flow)
    assert response.status_code == 201, response.text
    application = response.json()
    aid = application["id"]
    upload(api, flow["candidate"], "Version two")
    api["account"].put("/me", headers=flow["candidate"], json={"full_name": "Changed Name", "skills": ["New skill"]})
    detail = api["application"].get(f"/applications/{aid}", headers=flow["recruiter"]).json()
    assert detail["cv"]["sha256"] == flow["cv"]["sha256"]
    assert detail["candidate"]["full_name"] == "Test User"
    download = api["account"].get(f"/cvs/{flow['cv']['id']}/download?application_id={aid}", headers=flow["recruiter"])
    assert download.status_code == 200 and download.content == pdf()
    for status in ("Reviewing", "Interview", "Offered"):
        assert (
            api["application"]
            .patch(f"/applications/{aid}/status", headers=flow["recruiter"], json={"status": status})
            .status_code
            == 200
        )
    result = api["application"].get(f"/applications/{aid}", headers=flow["candidate"]).json()
    assert result["status"] == "Offered"
    assert [event["new_status"] for event in result["history"]] == ["Submitted", "Reviewing", "Interview", "Offered"]
    assert all(
        event["actor_id"] and datetime.fromisoformat(event["created_at"]).utcoffset() == timedelta(0)
        for event in result["history"]
    )
    assert (
        api["application"]
        .patch(f"/applications/{aid}/status", headers=flow["candidate"], json={"status": "Withdrawn"})
        .status_code
        == 409
    )


def test_roles_and_resource_ownership(api, flow):
    attacker, _, _ = register(api, "Recruiter")
    other_candidate, _, _ = register(api)
    company(api, attacker)
    other_job = job(api, attacker)
    assert api["job"].post("/jobs", headers=flow["candidate"], json={}).status_code == 403
    assert (
        api["job"].put(f"/companies/{flow['company']['id']}", headers=attacker, json={"name": "Hijacked"}).status_code
        == 404
    )
    assert api["job"].get(f"/jobs/{flow['job']['id']}/manage", headers=attacker).status_code == 404
    assert (
        api["job"].patch(f"/jobs/{flow['job']['id']}/status", headers=attacker, json={"status": "Closed"}).status_code
        == 404
    )
    assert submit(api, flow, candidate_id="forged").status_code == 422
    aid = submit(api, flow).json()["id"]
    for headers in (attacker, other_candidate):
        assert api["application"].get(f"/applications/{aid}", headers=headers).status_code == 404
        assert (
            api["application"]
            .patch(f"/applications/{aid}/status", headers=headers, json={"status": "Reviewing"})
            .status_code
            == 404
        )
        assert api["account"].get(
            f"/cvs/{flow['cv']['id']}/download?application_id={aid}", headers=headers
        ).status_code in (403, 404)
    assert api["application"].get(f"/applications?job_id={flow['job']['id']}", headers=attacker).status_code == 404
    assert api["account"].get(f"/cvs/{flow['cv']['id']}/download", headers=flow["recruiter"]).status_code == 403
    assert api["account"].get(f"/cvs/{flow['cv']['id']}/snapshot", headers=other_candidate).status_code == 404
    assert api["application"].get("/applications", headers=other_candidate).json() == []
    assert (
        api["application"]
        .post("/applications", headers=other_candidate, json={"job_id": other_job["id"], "cv_id": flow["cv"]["id"]})
        .status_code
        == 404
    )
    other_cv = upload(api, flow["candidate"], "Not submitted")
    assert (
        api["account"]
        .get(f"/cvs/{other_cv['id']}/download?application_id={aid}", headers=flow["recruiter"])
        .status_code
        == 403
    )


@pytest.mark.parametrize("state", ["Draft", "Closed", "Expired"])
def test_non_accepting_jobs(api, flow, system, state):
    draft = job(api, flow["recruiter"], publish=False)
    flow["job"] = draft
    if state != "Draft":
        api["job"].patch(f"/jobs/{draft['id']}/status", headers=flow["recruiter"], json={"status": "Published"})
    if state == "Closed":
        api["job"].patch(f"/jobs/{draft['id']}/status", headers=flow["recruiter"], json={"status": "Closed"})
    if state == "Expired":
        from sqlalchemy.orm import Session
        from services.job.models import Job

        with Session(system["modules"]["job"].engine) as db:
            db.get(Job, draft["id"]).deadline = now() - timedelta(days=1)
            db.commit()
    assert submit(api, flow).status_code == 409
    assert not any(item["id"] == draft["id"] for item in api["job"].get("/jobs?limit=100").json())
    if state == "Draft":
        assert api["job"].get(f"/jobs/{draft['id']}").status_code == 404


def test_duplicate_concurrent_and_after_withdrawal(api, flow, system):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: submit(api, flow), range(4)))
    assert sorted(response.status_code for response in responses) == [201, 409, 409, 409]
    aid = next(response.json()["id"] for response in responses if response.status_code == 201)
    assert (
        api["application"]
        .patch(f"/applications/{aid}/status", headers=flow["candidate"], json={"status": "Withdrawn"})
        .status_code
        == 200
    )
    assert submit(api, flow).status_code == 409
    from services.application.models import Application

    with system["modules"]["application"].engine.connect() as connection:
        count = connection.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.job_id == flow["job"]["id"], Application.candidate_id == flow["candidate_user"]["id"])
        )
    assert count == 1


@pytest.mark.parametrize("state", ["Submitted", "Reviewing", "Interview"])
def test_withdrawal_rules_and_invalid_transitions(api, flow, state):
    aid = submit(api, flow).json()["id"]
    path = f"/applications/{aid}/status"
    assert api["application"].patch(path, headers=flow["recruiter"], json={"status": "Offered"}).status_code == 409
    assert api["application"].patch(path, headers=flow["candidate"], json={"status": "Reviewing"}).status_code == 409
    assert api["application"].patch(path, headers=flow["recruiter"], json={"status": "Withdrawn"}).status_code == 409
    if state in ("Reviewing", "Interview"):
        api["application"].patch(path, headers=flow["recruiter"], json={"status": "Reviewing"})
    if state == "Interview":
        api["application"].patch(path, headers=flow["recruiter"], json={"status": "Interview"})
    assert api["application"].patch(path, headers=flow["candidate"], json={"status": "Withdrawn"}).status_code == 200
    assert api["application"].patch(path, headers=flow["recruiter"], json={"status": "Rejected"}).status_code == 409


@pytest.mark.parametrize("state", ["Submitted", "Reviewing", "Interview"])
def test_rejection_is_terminal(api, flow, state):
    aid = submit(api, flow).json()["id"]
    path = f"/applications/{aid}/status"
    if state in ("Reviewing", "Interview"):
        api["application"].patch(path, headers=flow["recruiter"], json={"status": "Reviewing"})
    if state == "Interview":
        api["application"].patch(path, headers=flow["recruiter"], json={"status": "Interview"})
    assert api["application"].patch(path, headers=flow["recruiter"], json={"status": "Rejected"}).status_code == 200
    assert api["application"].patch(path, headers=flow["candidate"], json={"status": "Withdrawn"}).status_code == 409


def test_concurrent_status_updates_keep_history_consistent(api, flow):
    aid = submit(api, flow).json()["id"]

    def transition(status):
        return api["application"].patch(
            f"/applications/{aid}/status", headers=flow["recruiter"], json={"status": status}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(transition, ["Reviewing", "Rejected"]))
    assert all(response.status_code in (200, 409) for response in responses)
    detail = api["application"].get(f"/applications/{aid}", headers=flow["candidate"]).json()
    for before, after in zip(detail["history"], detail["history"][1:]):
        assert before["new_status"] == after["old_status"]
    assert detail["status"] == detail["history"][-1]["new_status"]


@pytest.mark.parametrize("kind,code", [("text", 422), ("fake", 422), ("large", 413), ("encrypted", 422)])
def test_invalid_files(api, kind, code):
    headers, _, _ = register(api)
    content, mime = b"Not a PDF", "text/plain" if kind == "text" else "application/pdf"
    if kind == "large":
        content = b"%PDF-" + b"0" * (5 * 1024 * 1024)
    if kind == "encrypted":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("secret")
        output = io.BytesIO()
        writer.write(output)
        content = output.getvalue()
    response = api["account"].post(
        "/cvs", headers=headers, data={"name": "bad"}, files={"file": ("bad.pdf", content, mime)}
    )
    assert response.status_code == code
    assert api["account"].get("/cvs", headers=headers).json() == []


def test_dependency_unavailable_does_not_create_application(api, flow, monkeypatch):
    def fail(**kwargs):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(httpx, "Client", fail)
    response = submit(api, flow)
    assert response.status_code == 503
    assert api["application"].get("/applications", headers=flow["candidate"]).json() == []


def test_dependency_500_is_controlled(api, flow, monkeypatch):
    original = httpx.Client
    # api fixture wraps Client; use an isolated raw class captured through inheritance.
    from fastapi.testclient import TestClient

    raw_client = TestClient.__bases__[0]
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: raw_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(500, text="private database stack")), **kwargs
        ),
    )
    response = submit(api, flow)
    assert response.status_code == 503
    assert "private" not in response.text
    monkeypatch.setattr(httpx, "Client", original)


def test_database_failure_does_not_report_success(api, flow, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    def fail_commit(self):
        raise OperationalError("secret SQL", {}, Exception("private details"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = submit(api, flow)
    assert response.status_code == 503
    assert "private" not in response.text and "SQL" not in response.text
    assert api["application"].get("/applications", headers=flow["candidate"]).json() == []


def test_health_and_migration_schema(api, system):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    for name, client in api.items():
        assert client.get("/health").status_code == 200
        module = __import__(f"services.{name}.models", fromlist=["Base"])
        with system["modules"][name].engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), module.Base.metadata) == []
