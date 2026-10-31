import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.infrastructure import str_enum


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled)


class Job(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created_at", "status", "created_at"),)

    job_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(str_enum(JobStatus, "job_status"), default=JobStatus.queued, nullable=False)
    server_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"),
                                                        index=True)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    cancellable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    logs: Mapped[list["JobLog"]] = relationship(back_populates="job", cascade="all, delete-orphan",
                                                order_by="JobLog.id", lazy="select")


class JobLog(Base):
    __tablename__ = "job_logs"
    __table_args__ = (Index("ix_job_logs_job_id_id", "job_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job: Mapped[Job] = relationship(back_populates="logs")
