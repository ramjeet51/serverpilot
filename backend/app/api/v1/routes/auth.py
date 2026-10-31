from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from app.core.deps import CurrentUser, DbSession
from app.core.responses import ApiError, ok
from app.core.security import hash_password, verify_password
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserOut
from app.services import auth as auth_service
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Authenticate with email and password")
async def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> dict:
    result = await auth_service.login(db, request, response, body.email, body.password)
    return ok(result.model_dump(mode="json"))


@router.post("/refresh", summary="Rotate the refresh cookie and issue a new access token")
async def refresh(request: Request, response: Response, db: DbSession) -> dict:
    result = await auth_service.refresh(db, request, response)
    return ok(result.model_dump(mode="json"))


@router.post("/logout", summary="Revoke the current refresh session")
async def logout(request: Request, response: Response, db: DbSession) -> dict:
    await auth_service.logout(db, request, response)
    return ok({"logged_out": True})


@router.get("/me", summary="Current user profile and permissions")
async def me(user: CurrentUser) -> dict:
    return ok(UserOut.from_user(user).model_dump(mode="json"))


@router.post("/change-password", summary="Change the current user's password")
async def change_password(body: ChangePasswordRequest, request: Request, user: CurrentUser, db: DbSession) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        await record_audit(db, "auth.change_password", request=request, user=user, outcome="failure")
        raise ApiError(400, "invalid_password", "Current password is incorrect")
    if body.current_password == body.new_password:
        raise ApiError(400, "password_reused", "New password must differ from the current password")
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    await record_audit(db, "auth.change_password", request=request, user=user)
    return ok({"changed": True})
