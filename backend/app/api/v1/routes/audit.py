from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.deps import DbSession, require_permissions
from app.core.responses import Pagination, ok
from app.models import AuditLog, User
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", summary="Search the audit log")
async def list_audit(
    _: Annotated[User, Depends(require_permissions("audit:read"))],
    db: DbSession,
    page: Annotated[Pagination, Depends()],
    action: Annotated[str | None, Query(max_length=100)] = None,
    outcome: Annotated[str | None, Query(pattern="^(success|failure)$")] = None,
    since: datetime | None = None,
) -> dict:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"{action}%"))
    if outcome:
        query = query.where(AuditLog.outcome == outcome)
    if since:
        query = query.where(AuditLog.created_at >= since)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(AuditLog.id.desc()).offset(page.offset).limit(page.page_size))).scalars()
    return ok([AuditLogOut.model_validate(r).model_dump(mode="json") for r in rows], page.meta(total).model_dump())
