import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DbSession, require_permissions
from app.core.responses import ApiError, Pagination, ok
from app.core.security import hash_password
from app.models import Role, User
from app.schemas.accounts import AccountCreate, AccountUpdate, RoleOut
from app.schemas.auth import UserOut
from app.services.audit import record_audit

router = APIRouter(prefix="/accounts", tags=["accounts"])

Reader = Annotated[User, Depends(require_permissions("accounts:read"))]
Writer = Annotated[User, Depends(require_permissions("accounts:write"))]


async def _roles_by_name(db: AsyncSession, names: list[str]) -> list[Role]:
    roles = list((await db.execute(select(Role).where(Role.name.in_(names)))).scalars())
    if len(roles) != len(set(names)):
        raise ApiError(400, "unknown_role", "One or more roles do not exist; run the seed command")
    return roles


@router.get("/roles", summary="List roles and their permissions")
async def list_roles(_: Reader, db: DbSession) -> dict:
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars()
    return ok([RoleOut(name=r.name, description=r.description,
                       permissions=sorted(p.code for p in r.permissions)).model_dump() for r in roles])


@router.get("", summary="List platform user accounts")
async def list_accounts(_: Reader, db: DbSession, page: Annotated[Pagination, Depends()],
                        search: Annotated[str | None, Query(max_length=100)] = None) -> dict:
    query = select(User)
    if search:
        like = f"%{search.lower()}%"
        query = query.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    users = (await db.execute(query.order_by(User.created_at).offset(page.offset).limit(page.page_size))).scalars()
    return ok([UserOut.from_user(u).model_dump(mode="json") for u in users], page.meta(total).model_dump())


@router.post("", status_code=201, summary="Create a platform user account")
async def create_account(body: AccountCreate, request: Request, actor: Writer, db: DbSession) -> dict:
    exists = (await db.execute(select(User.id).where(func.lower(User.email) == body.email.lower()))).first()
    if exists:
        raise ApiError(409, "conflict", "An account with this email already exists")
    user = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password),
                roles=await _roles_by_name(db, body.roles))
    db.add(user)
    await db.flush()
    await record_audit(db, "accounts.create", request=request, user=actor, resource_type="user",
                       resource_id=str(user.id), details={"email": user.email, "roles": body.roles})
    await db.refresh(user)
    return ok(UserOut.from_user(user).model_dump(mode="json"))


@router.patch("/{user_id}", summary="Update a platform user account")
async def update_account(user_id: uuid.UUID, body: AccountUpdate, request: Request, actor: Writer, db: DbSession) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", "Account not found")
    if user.id == actor.id and (body.is_active is False or (body.roles is not None and "admin" not in body.roles)):
        raise ApiError(400, "self_lockout", "You cannot deactivate yourself or remove your own admin role")
    changes = body.model_dump(exclude_none=True)
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.roles is not None:
        user.roles = await _roles_by_name(db, body.roles)
    await record_audit(db, "accounts.update", request=request, user=actor, resource_type="user",
                       resource_id=str(user.id), details=changes)
    await db.refresh(user)
    return ok(UserOut.from_user(user).model_dump(mode="json"))
