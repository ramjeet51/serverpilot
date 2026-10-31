from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import EmailAddress

from app.schemas.auth import validate_password_strength

RoleName = Literal["admin", "operator", "viewer"]


class AccountCreate(BaseModel):
    email: EmailAddress
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=12, max_length=256)
    roles: list[RoleName] = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def _strength(cls, value: str) -> str:
        return validate_password_strength(value)


class AccountUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    roles: list[RoleName] | None = Field(default=None, min_length=1)


class RoleOut(BaseModel):
    name: str
    description: str
    permissions: list[str]
