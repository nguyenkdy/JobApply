import hashlib
import io
import os
from datetime import timedelta
from pathlib import Path
from typing import Literal

import jwt
from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import EmailStr, Field
from pypdf import PdfReader
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.runtime import Input, create_api, database, identity, now, remote, role, secret, uid, utc
from .models import CV, User

engine, session = database("account")
app = create_api("Account Service", engine)
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash("not-a-real-user-password")
candidate = role("Candidate")
cv_root = Path(os.environ.get("CV_STORAGE_PATH", "/data/cvs"))


class Register(Input):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["Candidate", "Recruiter"]


class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Profile(Input):
    full_name: str = Field(min_length=2, max_length=120)
    bio: str = Field(default="", max_length=3000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    location: str = Field(default="", max_length=120)
    contact: str = Field(default="", max_length=255)


def profile(user):
    return {
        key: getattr(user, key) for key in ("id", "email", "role", "full_name", "bio", "skills", "location", "contact")
    }


def cv_info(cv):
    return {
        "id": cv.id,
        "name": cv.name,
        "sha256": cv.sha256,
        "size": cv.size,
        "created_at": utc(cv.created_at),
        "download_url": f"/api/account/cvs/{cv.id}/download",
    }


def current_user(db, user):
    record = db.get(User, user.id)
    if not record:
        raise HTTPException(401, "Tài khoản không còn tồn tại")
    return record


@app.post("/auth/register", status_code=201)
def register(data: Register, db: Session = Depends(session)):
    record = User(
        email=str(data.email).lower(),
        password_hash=passwords.hash(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email này đã được đăng ký") from None
    return profile(record)


@app.post("/auth/login")
def login(data: Login, db: Session = Depends(session)):
    record = db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = passwords.verify(data.password, record.password_hash if record else dummy_hash)
    if not record or not valid:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    issued = now()
    token = jwt.encode(
        {
            "sub": record.id,
            "role": record.role,
            "iat": issued,
            "exp": issued + timedelta(minutes=int(os.environ.get("TOKEN_MINUTES", "120"))),
            "iss": "jobapply-account",
            "aud": "jobapply",
        },
        secret(),
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer", "user": profile(record)}


@app.get("/me")
def me(user=Depends(identity), db: Session = Depends(session)):
    return profile(current_user(db, user))


@app.put("/me")
def update_profile(data: Profile, user=Depends(candidate), db: Session = Depends(session)):
    record = current_user(db, user)
    if any(not skill or len(skill) > 60 for skill in data.skills):
        raise HTTPException(422, "Mỗi kỹ năng cần từ 1 đến 60 ký tự")
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    db.commit()
    return profile(record)


@app.get("/cvs")
def list_cvs(user=Depends(candidate), db: Session = Depends(session)):
    return [cv_info(cv) for cv in db.scalars(select(CV).where(CV.owner_id == user.id).order_by(CV.created_at.desc()))]


@app.post("/cvs", status_code=201)
def upload_cv(
    name: str = Form(min_length=1, max_length=120),
    file: UploadFile = File(),
    user=Depends(candidate),
    db: Session = Depends(session),
):
    current_user(db, user)
    if not name.strip():
        raise HTTPException(422, "Vui lòng đặt tên phiên bản CV")
    if file.content_type != "application/pdf":
        raise HTTPException(422, "Chỉ chấp nhận file PDF")
    content = file.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CV không được vượt quá 5 MB")
    try:
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
            raise ValueError()
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) < 1:
            raise ValueError()
    except Exception:
        raise HTTPException(422, "PDF không hợp lệ hoặc được mã hóa") from None
    key = uid() + ".pdf"
    cv_root.mkdir(parents=True, exist_ok=True)
    path = cv_root / key
    try:
        with path.open("xb") as output:
            output.write(content)
        record = CV(
            owner_id=user.id,
            name=name.strip(),
            storage_key=key,
            sha256=hashlib.sha256(content).hexdigest(),
            size=len(content),
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return cv_info(record)


@app.get("/cvs/{cv_id}/snapshot")
def snapshot(cv_id: str, user=Depends(candidate), db: Session = Depends(session)):
    cv = db.get(CV, cv_id)
    if not cv or cv.owner_id != user.id:
        raise HTTPException(404, "Không tìm thấy CV của bạn")
    return {"cv": cv_info(cv), "candidate": profile(current_user(db, user))}


@app.get("/cvs/{cv_id}/download")
def download(cv_id: str, application_id: str | None = None, user=Depends(identity), db: Session = Depends(session)):
    cv = db.get(CV, cv_id)
    if not cv:
        raise HTTPException(404, "Không tìm thấy CV")
    if cv.owner_id != user.id:
        if user.role != "Recruiter" or not application_id:
            raise HTTPException(403, "Bạn không có quyền tải CV này")
        # Application Service checks company ownership with Job Service using this same JWT.
        from uuid import UUID

        try:
            UUID(application_id)
        except ValueError:
            raise HTTPException(422, "Mã hồ sơ không hợp lệ") from None
        access = remote("application", f"/applications/{application_id}/cv-access", user)
        if access["cv_id"] != cv.id or access["candidate_id"] != cv.owner_id:
            raise HTTPException(403, "CV không thuộc hồ sơ được phép xem")
    path = cv_root / cv.storage_key
    if not path.is_file():
        raise HTTPException(404, "File CV không còn trên ổ lưu trữ")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"cv-{cv.id}.pdf",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
