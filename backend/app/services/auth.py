import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.middleware import client_ip
from app.core.redis import get_async_redis
from app.core.responses import ApiError
from app.core.security import (DUMMY_PASSWORD_HASH, create_token, decode_token, generate_csrf_token,
                               verify_password)
from app.models import User
from app.schemas.auth import TokenResponse, UserOut
from app.services.audit import record_audit

REFRESH_COOKIE = "sp_refresh"
CSRF_COOKIE = "sp_csrf"
CSRF_HEADER = "x-csrf-token"
AUTH_COOKIE_PATH = "/api/v1/auth"


def _refresh_key(jti: str) -> str:
    return f"sp:refresh:{jti}"


def _login_rate_key(request: Request, email: str) -> str:
    return f"sp:rl:login:{client_ip(request)}:{email.lower()}"


async def _check_login_rate_limit(request: Request, email: str) -> None:
    s = get_settings()
    key = _login_rate_key(request, email)
    r = get_async_redis()
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, s.login_rate_limit_window_seconds)
    if count > s.login_rate_limit_attempts:
        ttl = await r.ttl(key)
        raise ApiError(429, "rate_limited", "Too many login attempts. Try again later.",
                       {"retry_after_seconds": max(ttl, 1)})


async def _issue_session(user: User, response: Response) -> TokenResponse:
    s = get_settings()
    access, _, _ = create_token(str(user.id), "access")
    refresh, jti, refresh_exp = create_token(str(user.id), "refresh")
    csrf = generate_csrf_token()
    ttl = int((refresh_exp - datetime.now(UTC)).total_seconds())
    await get_async_redis().set(_refresh_key(jti), f"{user.id}:{csrf}", ex=ttl)
    cookie_args = dict(httponly=True, secure=s.cookie_secure, samesite="strict", path=AUTH_COOKIE_PATH, max_age=ttl)
    response.set_cookie(REFRESH_COOKIE, refresh, **cookie_args)
    response.set_cookie(CSRF_COOKIE, csrf, **cookie_args)
    return TokenResponse(access_token=access, expires_in=s.jwt_access_token_expire_minutes * 60, csrf_token=csrf,
                         user=UserOut.from_user(user))


async def login(db: AsyncSession, request: Request, response: Response, email: str, password: str) -> TokenResponse:
    s = get_settings()
    await _check_login_rate_limit(request, email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none()
    now = datetime.now(UTC)

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        await record_audit(db, "auth.login", request=request, actor_label=email, outcome="failure",
                           details={"reason": "unknown_user"})
        raise ApiError(401, "invalid_credentials", "Invalid email or password")

    if user.locked_until and user.locked_until > now:
        await record_audit(db, "auth.login", request=request, user=user, outcome="failure", details={"reason": "locked"})
        raise ApiError(423, "account_locked", "Account temporarily locked due to repeated failed logins")

    if not verify_password(password, user.password_hash) or not user.is_active:
        reason = "inactive" if user.is_active is False else "bad_password"
        user.failed_login_count += 1
        if user.failed_login_count >= s.account_lockout_threshold:
            user.locked_until = now + timedelta(minutes=s.account_lockout_minutes)
            user.failed_login_count = 0
        await record_audit(db, "auth.login", request=request, user=user, outcome="failure", details={"reason": reason})
        raise ApiError(401, "invalid_credentials", "Invalid email or password")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    await get_async_redis().delete(_login_rate_key(request, email))
    await record_audit(db, "auth.login", request=request, user=user)
    return await _issue_session(user, response)


def _verify_csrf(request: Request) -> str:
    header = request.headers.get(CSRF_HEADER)
    cookie = request.cookies.get(CSRF_COOKIE)
    if not header or not cookie or header != cookie:
        raise ApiError(403, "csrf_failed", "CSRF token missing or invalid")
    return header


async def refresh(db: AsyncSession, request: Request, response: Response) -> TokenResponse:
    csrf = _verify_csrf(request)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise ApiError(401, "not_authenticated", "No refresh session")
    try:
        payload = decode_token(token, "refresh")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise ApiError(401, "invalid_token", "Invalid or expired refresh token") from exc

    # Single-use refresh tokens: GETDEL makes rotation atomic, so a replayed token is rejected.
    stored = await get_async_redis().getdel(_refresh_key(payload["jti"]))
    if stored != f"{user_id}:{csrf}":
        raise ApiError(401, "invalid_token", "Refresh session revoked or already used")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise ApiError(401, "invalid_token", "User is inactive or no longer exists")
    return await _issue_session(user, response)


async def logout(db: AsyncSession, request: Request, response: Response) -> None:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        _verify_csrf(request)
        try:
            payload = decode_token(token, "refresh")
            await get_async_redis().delete(_refresh_key(payload["jti"]))
            user = (await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))).scalar_one_or_none()
            await record_audit(db, "auth.logout", request=request, user=user)
        except (jwt.PyJWTError, ValueError):
            pass
    for name in (REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path=AUTH_COOKIE_PATH)
