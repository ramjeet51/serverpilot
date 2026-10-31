import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ServerScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_id: uuid.UUID


class SoftwareQuery(ServerScope):
    software_id: str = Field(min_length=1, max_length=64)


class LibraryQuery(ServerScope):
    query: str = Field(min_length=1, max_length=40)


class ArchiveInstall(ServerScope):
    package: str = Field(min_length=2, max_length=61)
    confirm: bool = False


class SoftwareChange(SoftwareQuery):
    action: Literal["install", "remove", "update"]
    version: str | None = Field(default=None, max_length=80)
    confirm: bool = False


class ServiceQuery(ServerScope):
    unit: str = Field(min_length=1, max_length=128)


class ServiceChange(ServiceQuery):
    action: Literal["restart", "enable", "disable"]
    confirm: bool = False
