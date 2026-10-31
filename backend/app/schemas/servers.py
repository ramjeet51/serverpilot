import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.infrastructure import AgentStatus, ServerStatus


class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    hostname: str = Field(min_length=1, max_length=255)
    ip_address: str = Field(min_length=1, max_length=45)
    environment: str = Field(default="production", max_length=32)
    description: str = Field(default="", max_length=2000)


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    hostname: str
    ip_address: str | None
    environment: str
    description: str
    status: ServerStatus
    os_name: str | None
    os_version: str | None
    kernel_version: str | None
    cpu_cores: int | None
    memory_total_bytes: int | None
    disk_total_bytes: int | None
    last_seen_at: datetime | None
    agent_status: AgentStatus | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    disk_percent: float | None = None
    created_at: datetime


class RegistrationOut(BaseModel):
    server: ServerOut
    registration_token: str
    gateway_url: str
    expires_at: datetime
