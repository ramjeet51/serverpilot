import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import ApiError
from app.core.security import decode_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def load_user_from_access_token(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_token(token, "access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise ApiError(401, "invalid_token", "Invalid or expired access token") from exc
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise ApiError(401, "invalid_token", "User is inactive or no longer exists")
    return user


async def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "not_authenticated", "Authentication required")
    user = await load_user_from_access_token(db, credentials.credentials)
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def has_permissions(user: User, *codes: str) -> bool:
    return user.is_superuser or set(codes).issubset(user.permission_codes)


def require_permissions(*codes: str) -> Callable:
    async def _checker(user: CurrentUser) -> User:
        if not has_permissions(user, *codes):
            raise ApiError(403, "forbidden", "You do not have permission to perform this action",
                           {"required": list(codes)})
        return user

    return _checker
