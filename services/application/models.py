from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from shared.runtime import now, uid


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    cv_id: Mapped[str] = mapped_column(String(36))
    job_snapshot: Mapped[dict] = mapped_column(JSON)
    candidate_snapshot: Mapped[dict] = mapped_column(JSON)
    cv_snapshot: Mapped[dict] = mapped_column(JSON)
    introduction: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Submitted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class History(Base):
    __tablename__ = "history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_role: Mapped[str] = mapped_column(String(20))
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
