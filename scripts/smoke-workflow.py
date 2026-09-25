"""Real HTTP workflow on VM. Creates isolated demo records; no direct DB access."""

import argparse
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from pypdf import PdfWriter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://frontend")
    args = parser.parse_args()
    suffix = uuid4().hex[:12]
    password = uuid4().hex
    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20)

    def request(method, path, expected=200, token=None, **kwargs):
        response = client.request(method, path, headers={"Authorization": f"Bearer {token}"} if token else {}, **kwargs)
        if response.status_code != expected:
            # Do not print response bodies, credentials or tokens.
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}, yêu cầu {expected}")
        return response

    def account(role):
        email = f"smoke-{role.lower()}-{suffix}@example.com"
        response = request(
            "POST",
            "/api/account/auth/register",
            201,
            json={"email": email, "password": password, "full_name": f"Smoke {role}", "role": role},
        )
        user_id = response.json()["id"]
        token = request("POST", "/api/account/auth/login", json={"email": email, "password": password}).json()[
            "access_token"
        ]
        return token, user_id

    try:
        for service in ("account", "job", "application"):
            assert request("GET", f"/api/{service}/health").json()["status"] == "ok"
        recruiter, _ = account("Recruiter")
        candidate, candidate_id = account("Candidate")
        request("POST", "/api/job/companies", 201, recruiter, json={"name": f"Smoke Company {suffix}"})
        job = request(
            "POST",
            "/api/job/jobs",
            201,
            recruiter,
            json={
                "title": f"Smoke Python {suffix}",
                "description": "Fake smoke workflow position",
                "requirements": "Python and SQL experience",
                "location": "Hà Nội",
                "level": "Junior",
                "work_mode": "Remote",
                "deadline": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            },
        ).json()
        jid = job["id"]
        request("PATCH", f"/api/job/jobs/{jid}/status", token=recruiter, json={"status": "Published"})
        results = request("GET", "/api/job/jobs", params={"q": suffix}).json()
        assert any(item["id"] == jid for item in results)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_metadata({"/Title": "Fake smoke CV"})
        output = io.BytesIO()
        writer.write(output)
        cv = request(
            "POST",
            "/api/account/cvs",
            201,
            candidate,
            data={"name": "Smoke CV"},
            files={"file": ("smoke.pdf", output.getvalue(), "application/pdf")},
        ).json()
        application = request(
            "POST",
            "/api/application/applications",
            201,
            candidate,
            json={"job_id": jid, "cv_id": cv["id"], "introduction": "Fake smoke test"},
        ).json()
        aid = application["id"]
        request("POST", "/api/application/applications", 409, candidate, json={"job_id": jid, "cv_id": cv["id"]})
        applicants = request("GET", "/api/application/applications", token=recruiter, params={"job_id": jid}).json()
        assert any(item["id"] == aid for item in applicants)
        content = request("GET", application["download_url"], token=recruiter).content
        assert content == output.getvalue()
        request("PATCH", f"/api/application/applications/{aid}/status", token=recruiter, json={"status": "Reviewing"})
        result = request("GET", f"/api/application/applications/{aid}", token=candidate).json()
        assert result["status"] == "Reviewing" and result["candidate_id"] == candidate_id
        assert [event["new_status"] for event in result["history"]] == ["Submitted", "Reviewing"]
        request("PATCH", f"/api/application/applications/{aid}/status", token=candidate, json={"status": "Withdrawn"})
        request("PATCH", f"/api/job/jobs/{jid}/status", token=recruiter, json={"status": "Closed"})
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "workflow": "register-company-publish-search-upload-submit-download-review-withdraw",
                    "demo_suffix": suffix,
                }
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
