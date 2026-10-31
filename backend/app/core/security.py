"""Password hashing and JWT handling."""

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]


def _prehash(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; SHA-256 pre-hashing keeps the full password significant.
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except ValueError:
        return False


# Used to equalise timing when the user does not exist.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def create_token(subject: str, token_type: TokenType, extra: dict[str, Any] | None = None) -> tuple[str, str, datetime]:
    s = get_settings()
    now = datetime.now(UTC)
    if token_type == "access":
        expires = now + timedelta(minutes=s.jwt_access_token_expire_minutes)
    else:
        expires = now + timedelta(days=s.jwt_refresh_token_expire_days)
    jti = uuid.uuid4().hex
    payload = {"sub": subject, "type": token_type, "jti": jti, "iat": now, "exp": expires, "iss": s.app_name}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, s.jwt_secret_key.get_secret_value(), algorithm=s.jwt_algorithm)
    return token, jti, expires


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    s = get_settings()
    payload = jwt.decode(
        token,
        s.jwt_secret_key.get_secret_value(),
        algorithms=[s.jwt_algorithm],
        issuer=s.app_name,
        options={"require": ["sub", "type", "jti", "exp", "iat"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
