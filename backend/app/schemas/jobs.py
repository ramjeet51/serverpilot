import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.jobs import JobStatus


class DiagnosticsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SleepTestParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: int = Field(default=10, ge=1, le=300)
    fail_at_end: bool = False


class DiagnosticsJob(BaseModel):
    job_type: Literal["platform.diagnostics"]
    params: DiagnosticsParams = DiagnosticsParams()


class SleepTestJob(BaseModel):
    job_type: Literal["platform.sleep_test"]
    params: SleepTestParams = SleepTestParams()


JobCreate = Annotated[DiagnosticsJob | SleepTestJob, Field(discriminator="job_type")]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: JobStatus
    server_id: uuid.UUID | None
    params: dict[str, Any]
    result: dict[str, Any] | None
    error_message: str | None
    progress: int
    attempts: int
    max_retries: int
    timeout_seconds: int
    cancellable: bool
    cancel_requested: bool
    created_by_id: uuid.UUID | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: uuid.UUID
    level: str
    message: str
    data: dict[str, Any] | None
    created_at: datetime


class JobStats(BaseModel):
    queued: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    failed_last_24h: int = 0
