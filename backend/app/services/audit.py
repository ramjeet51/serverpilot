import logging
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.middleware import client_ip
from app.models import AuditLog, User

logger = logging.getLogger("serverpilot.audit")


async def record_audit(
    db: AsyncSession,
    action: str,
    *,
    request: Request | None = None,
    user: User | None = None,
    actor_label: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    entry = AuditLog(
        actor_user_id=user.id if user else None,
        actor_type="user" if user else "anonymous",
        actor_label=actor_label or (user.email if user else None),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        ip_address=client_ip(request) if request else None,
        user_agent=(request.headers.get("user-agent", "")[:512] or None) if request else None,
        details=details,
    )
    db.add(entry)
    if commit:
        await db.commit()
    logger.info("audit", extra={"action": action, "outcome": outcome, "actor": entry.actor_label,
                                "resource_type": resource_type, "resource_id": resource_id})


def record_audit_sync(session, action: str, *, user_id, actor_label: str | None, resource_type: str | None,
                      resource_id: str | None, outcome: str, details: dict[str, Any] | None) -> None:
    session.add(AuditLog(
        actor_user_id=user_id, actor_type="user" if user_id else "system", actor_label=actor_label,
        action=action, resource_type=resource_type, resource_id=resource_id, outcome=outcome, details=details,
    ))
    session.commit()
