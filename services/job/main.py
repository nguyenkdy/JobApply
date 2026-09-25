from datetime import datetime
from typing import Literal
from fastapi import Depends, HTTPException, Query
from pydantic import Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from shared.runtime import Input, create_api, database, now, role, utc
from .models import Company, Job

engine, session = database("job")
app = create_api("Job Service", engine)
recruiter = role("Recruiter")


class CompanyInput(Input):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=10000)
    location: str = Field(default="", max_length=120)
    website: str = Field(default="", max_length=255)

    @field_validator("website")
    @classmethod
    def valid_website(cls, value):
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Website phải bắt đầu bằng https:// hoặc http://")
        return value


class JobInput(Input):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=20000)
    requirements: str = Field(min_length=10, max_length=20000)
    location: str = Field(min_length=2, max_length=120)
    level: Literal["Intern", "Junior", "Middle", "Senior", "Lead"]
    work_mode: Literal["Onsite", "Hybrid", "Remote"]
    salary: str = Field(default="", max_length=120)
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def valid_deadline(cls, value):
        if value.tzinfo is None:
            raise ValueError("Hạn ứng tuyển cần có múi giờ")
        return utc(value)


class Status(Input):
    status: Literal["Published", "Closed"]


def company_info(company):
    return {key: getattr(company, key) for key in ("id", "name", "description", "location", "website")}


def job_info(record, db):
    result = {
        key: getattr(record, key)
        for key in (
            "id",
            "company_id",
            "title",
            "description",
            "requirements",
            "location",
            "level",
            "work_mode",
            "salary",
            "status",
        )
    }
    result.update(
        deadline=utc(record.deadline),
        created_at=utc(record.created_at),
        company=company_info(db.get(Company, record.company_id)),
    )
    return result


def owned_company(db, user):
    company = db.scalar(select(Company).where(Company.owner_id == user.id))
    if not company:
        raise HTTPException(404, "Bạn chưa tạo hồ sơ công ty")
    return company


def owned_job(db, user, job_id):
    record = db.get(Job, job_id)
    if not record or db.get(Company, record.company_id).owner_id != user.id:
        raise HTTPException(404, "Không tìm thấy job thuộc công ty của bạn")
    return record


@app.get("/companies/mine")
def my_company(user=Depends(recruiter), db: Session = Depends(session)):
    company = db.scalar(select(Company).where(Company.owner_id == user.id))
    return company_info(company) if company else None


@app.post("/companies", status_code=201)
def create_company(data: CompanyInput, user=Depends(recruiter), db: Session = Depends(session)):
    company = Company(owner_id=user.id, **data.model_dump())
    db.add(company)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Mỗi recruiter chỉ sở hữu một công ty trong MVP") from None
    return company_info(company)


@app.put("/companies/{company_id}")
def update_company(company_id: str, data: CompanyInput, user=Depends(recruiter), db: Session = Depends(session)):
    company = owned_company(db, user)
    if company.id != company_id:
        raise HTTPException(404, "Không tìm thấy công ty của bạn")
    for key, value in data.model_dump().items():
        setattr(company, key, value)
    db.commit()
    return company_info(company)


@app.get("/jobs")
def search(
    q: str = Query(default="", max_length=160),
    location: str = Query(default="", max_length=120),
    level: str = "",
    work_mode: str = "",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(session),
):
    query = select(Job).join(Company).where(Job.status == "Published", Job.deadline > now())
    if q:
        query = query.where(
            or_(
                Job.title.icontains(q, autoescape=True),
                Job.description.icontains(q, autoescape=True),
                Company.name.icontains(q, autoescape=True),
            )
        )
    if location:
        query = query.where(Job.location.icontains(location, autoescape=True))
    if level:
        query = query.where(Job.level == level)
    if work_mode:
        query = query.where(Job.work_mode == work_mode)
    records = db.scalars(query.order_by(Job.created_at.desc(), Job.id).offset(offset).limit(limit))
    return [job_info(record, db) for record in records]


@app.get("/jobs/mine")
def my_jobs(user=Depends(recruiter), db: Session = Depends(session)):
    company = db.scalar(select(Company).where(Company.owner_id == user.id))
    if not company:
        return []
    return [
        job_info(record, db)
        for record in db.scalars(select(Job).where(Job.company_id == company.id).order_by(Job.created_at.desc()))
    ]


@app.post("/jobs", status_code=201)
def create_job(data: JobInput, user=Depends(recruiter), db: Session = Depends(session)):
    company = owned_company(db, user)
    record = Job(company_id=company.id, **data.model_dump())
    db.add(record)
    db.commit()
    return job_info(record, db)


@app.get("/jobs/{job_id}")
def detail(job_id: str, db: Session = Depends(session)):
    record = db.get(Job, job_id)
    if not record or record.status == "Draft":
        raise HTTPException(404, "Không tìm thấy việc làm")
    return job_info(record, db)


@app.get("/jobs/{job_id}/manage")
def manage(job_id: str, user=Depends(recruiter), db: Session = Depends(session)):
    return job_info(owned_job(db, user, job_id), db)


@app.get("/jobs/{job_id}/eligibility")
def eligibility(job_id: str, user=Depends(role("Candidate")), db: Session = Depends(session)):
    record = db.get(Job, job_id)
    if not record:
        raise HTTPException(404, "Không tìm thấy việc làm")
    if record.status != "Published" or utc(record.deadline) <= now():
        raise HTTPException(409, "Việc làm này chưa mở, đã đóng hoặc đã hết hạn ứng tuyển")
    return job_info(record, db)


@app.put("/jobs/{job_id}")
def edit(job_id: str, data: JobInput, user=Depends(recruiter), db: Session = Depends(session)):
    record = owned_job(db, user, job_id)
    if record.status != "Draft":
        raise HTTPException(409, "Chỉ có thể chỉnh sửa job nháp")
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    db.commit()
    return job_info(record, db)


@app.patch("/jobs/{job_id}/status")
def change_status(job_id: str, data: Status, user=Depends(recruiter), db: Session = Depends(session)):
    # Lock serializes publish/close against each other in PostgreSQL.
    record = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
    owned_job(db, user, job_id)
    allowed = {"Draft": "Published", "Published": "Closed"}
    if allowed.get(record.status) != data.status:
        raise HTTPException(409, "Chuyển trạng thái job không hợp lệ")
    if data.status == "Published" and utc(record.deadline) <= now():
        raise HTTPException(409, "Hạn ứng tuyển phải ở tương lai")
    record.status = data.status
    db.commit()
    return job_info(record, db)
