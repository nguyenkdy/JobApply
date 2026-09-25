from typing import Literal
from uuid import UUID
from fastapi import Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from shared.runtime import Input, create_api, database, identity, remote, role, utc
from .models import Application, History

engine, session = database("application")
app = create_api("Application Service", engine)
TRANSITIONS = {
    "Submitted": {"Reviewing", "Rejected"},
    "Reviewing": {"Interview", "Rejected"},
    "Interview": {"Offered", "Rejected"},
}
WITHDRAWABLE = {"Submitted", "Reviewing", "Interview"}


class Submission(Input):
    job_id: UUID
    cv_id: UUID
    introduction: str = Field(default="", max_length=5000)


class Status(Input):
    status: Literal["Reviewing", "Interview", "Offered", "Rejected", "Withdrawn"]


def info(record):
    return {
        "id": record.id,
        "candidate_id": record.candidate_id,
        "job_id": record.job_id,
        "cv_id": record.cv_id,
        "job": record.job_snapshot,
        "candidate": record.candidate_snapshot,
        "cv": record.cv_snapshot,
        "introduction": record.introduction,
        "status": record.status,
        "created_at": utc(record.created_at),
        "download_url": f"/api/account/cvs/{record.cv_id}/download?application_id={record.id}",
    }


def authorize(record, user):
    if not record:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    if user.role == "Candidate":
        if record.candidate_id != user.id:
            raise HTTPException(404, "Không tìm thấy hồ sơ của bạn")
    else:
        remote("job", f"/jobs/{record.job_id}/manage", user)


@app.post("/applications", status_code=201)
def submit(data: Submission, user=Depends(role("Candidate")), db: Session = Depends(session)):
    job = remote("job", f"/jobs/{data.job_id}/eligibility", user)
    snapshot = remote("account", f"/cvs/{data.cv_id}/snapshot", user)
    record = Application(
        candidate_id=user.id,
        job_id=str(data.job_id),
        cv_id=str(data.cv_id),
        job_snapshot=job,
        candidate_snapshot=snapshot["candidate"],
        cv_snapshot=snapshot["cv"],
        introduction=data.introduction,
    )
    db.add(record)
    try:
        db.flush()
        db.add(
            History(
                application_id=record.id,
                actor_id=user.id,
                actor_role=user.role,
                old_status=None,
                new_status="Submitted",
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bạn đã ứng tuyển job này; mỗi ứng viên chỉ được nộp một lần") from None
    return info(record)


@app.get("/applications")
def list_applications(
    job_id: UUID | None = None, status: str = "", user=Depends(identity), db: Session = Depends(session)
):
    query = select(Application)
    if user.role == "Candidate":
        query = query.where(Application.candidate_id == user.id)
        if job_id:
            query = query.where(Application.job_id == str(job_id))
    else:
        if not job_id:
            raise HTTPException(422, "Chọn job để xem danh sách ứng viên")
        remote("job", f"/jobs/{job_id}/manage", user)
        query = query.where(Application.job_id == str(job_id))
    if status:
        query = query.where(Application.status == status)
    return [info(record) for record in db.scalars(query.order_by(Application.created_at.desc()))]


@app.get("/applications/{application_id}")
def detail(application_id: UUID, user=Depends(identity), db: Session = Depends(session)):
    record = db.get(Application, str(application_id))
    authorize(record, user)
    result = info(record)
    result["history"] = [
        {
            "actor_id": event.actor_id,
            "actor_role": event.actor_role,
            "old_status": event.old_status,
            "new_status": event.new_status,
            "created_at": utc(event.created_at),
        }
        for event in db.scalars(
            select(History).where(History.application_id == record.id).order_by(History.created_at, History.id)
        )
    ]
    return result


@app.get("/applications/{application_id}/cv-access")
def cv_access(application_id: UUID, user=Depends(role("Recruiter")), db: Session = Depends(session)):
    record = db.get(Application, str(application_id))
    authorize(record, user)
    return {"cv_id": record.cv_id, "candidate_id": record.candidate_id}


@app.patch("/applications/{application_id}/status")
def change_status(application_id: UUID, data: Status, user=Depends(identity), db: Session = Depends(session)):
    record = db.get(Application, str(application_id))
    authorize(record, user)
    previous = record.status
    valid = (
        (data.status == "Withdrawn" and previous in WITHDRAWABLE)
        if user.role == "Candidate"
        else data.status in TRANSITIONS.get(previous, set())
    )
    if not valid:
        raise HTTPException(409, "Chuyển trạng thái không hợp lệ hoặc hồ sơ đã kết thúc")
    # Compare-and-swap ensures concurrent recruiter/candidate writes cannot overwrite history.
    result = db.execute(
        update(Application)
        .where(Application.id == record.id, Application.status == previous)
        .values(status=data.status)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Hồ sơ vừa được cập nhật. Vui lòng tải lại.")
    db.add(
        History(
            application_id=record.id,
            actor_id=user.id,
            actor_role=user.role,
            old_status=previous,
            new_status=data.status,
        )
    )
    db.commit()
    db.refresh(record)
    return info(record)
