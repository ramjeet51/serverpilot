import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import EmailAddress


def validate_password_strength(value: str) -> str:
    checks = [any(c.islower() for c in value), any(c.isupper() for c in value), any(c.isdigit() for c in value),
              any(not c.isalnum() for c in value)]
    if sum(checks) < 3:
        raise ValueError("Password must contain at least three of: lowercase, uppercase, digit, symbol")
    return value


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    mfa_enabled: bool
    roles: list[str] = Field(validation_alias="role_names")
    permissions: list[str] = []
    last_login_at: datetime | None
    created_at: datetime

    @classmethod
    def from_user(cls, user) -> "UserOut":
        out = cls.model_validate(user)
        out.permissions = sorted(user.permission_codes)
        return out


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    csrf_token: str
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

    @field_validator("new_password")
    @classmethod
    def _strength(cls, value: str) -> str:
        return validate_password_strength(value)
