"""Infrastructure only; each service owns its engine, tables and business logic."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Identity(BaseModel):
    id: str
    role: str
    token: str


bearer = HTTPBearer(auto_error=False)


def secret():
    value = os.environ["JWT_SECRET"]
    if len(value) < 32 or value.startswith("CHANGE_ME"):
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return value


def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "Vui lòng đăng nhập", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(
            credentials.credentials,
            secret(),
            algorithms=["HS256"],
            audience="jobapply",
            issuer="jobapply-account",
            options={"require": ["sub", "role", "exp", "iat", "iss", "aud"]},
        )
        if claims["role"] not in ("Candidate", "Recruiter") or not claims["sub"]:
            raise jwt.InvalidTokenError()
        return Identity(id=claims["sub"], role=claims["role"], token=credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(
            401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn", headers={"WWW-Authenticate": "Bearer"}
        ) from None


def role(required):
    def dependency(user: Identity = Depends(identity)):
        if user.role != required:
            raise HTTPException(403, "Vai trò không được phép thực hiện thao tác này")
        return user

    return dependency


def database(service):
    url = os.environ[f"{service.upper()}_DATABASE_URL"]
    options = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=options)
    factory = sessionmaker(engine, expire_on_commit=False)

    def session():
        with factory() as db:
            yield db

    return engine, session


def create_api(title, engine):
    secret()
    app = FastAPI(title=title, version="1.0.0", root_path=os.environ.get("API_ROOT_PATH", ""))

    @app.get("/health")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": title}

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return JSONResponse(
            status_code=503, content={"detail": "Cơ sở dữ liệu tạm thời không khả dụng. Vui lòng thử lại."}
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        return JSONResponse(status_code=500, content={"detail": "Không thể xử lý yêu cầu. Vui lòng thử lại."})

    return app


def remote(service, path, user):
    """Forward a signed user token, never trust identity headers or bypass ACLs."""
    base = os.environ[f"{service.upper()}_SERVICE_URL"].rstrip("/")
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0, connect=2.0), follow_redirects=False) as client:
            response = client.get(base + path, headers={"Authorization": f"Bearer {user.token}"})
        if response.status_code >= 500:
            raise HTTPException(503, f"Dịch vụ {service} tạm thời không khả dụng")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", "Yêu cầu không được chấp nhận")
            except ValueError:
                detail = "Yêu cầu không được chấp nhận"
            raise HTTPException(response.status_code, detail)
        return response.json()
    except httpx.RequestError, ValueError:
        raise HTTPException(503, f"Không thể kết nối dịch vụ {service}. Vui lòng thử lại.") from None
