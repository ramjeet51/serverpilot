import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.deps import DbSession, require_permissions
from app.core.responses import ok
from app.models import ServiceInventory, User
from app.schemas.jobs import JobOut
from app.schemas.operations import ServerScope, ServiceChange, ServiceQuery
from app.services.audit import record_audit
from app.services.catalogue import SUGGESTED_UNITS, normalize_unit
from app.services.host_ops import begin_job, call_agent, require_server, save_services, validate_service_action

router = APIRouter(prefix="/services", tags=["services"])
Reader = Annotated[User, Depends(require_permissions("services:read"))]
Writer = Annotated[User, Depends(require_permissions("services:write"))]


def _row(item: ServiceInventory) -> dict:
    return {
        "unit": item.unit_name,
        "description": item.description,
        "active": item.active_state,
        "sub": item.sub_state,
        "enabled": item.unit_file_state,
        "suggested": item.unit_name in SUGGESTED_UNITS,
    }


@router.get("", summary="Last discovered services on a server")
async def inventory(_: Reader, db: DbSession, server_id: Annotated[uuid.UUID, Query()],
                    q: Annotated[str, Query(max_length=128)] = "") -> dict:
    await require_server(db, server_id)
    rows = (await db.execute(select(ServiceInventory).where(ServiceInventory.server_id == server_id)
                             .order_by(ServiceInventory.unit_name))).scalars()
    needle = q.strip().lower()
    data = [_row(row) for row in rows if not needle or needle in row.unit_name.lower() or needle in row.description.lower()]
    return ok(data)


@router.post("/refresh", summary="Discover systemd services on the server")
async def refresh(body: ServerScope, request: Request, user: Reader, db: DbSession) -> dict:
    await require_server(db, body.server_id)
    result = await call_agent(db, body.server_id, "services.list", {}, timeout=30)
    await save_services(db, body.server_id, result.get("services") or [])
    await record_audit(db, "services.refresh", request=request, user=user, resource_type="server",
                       resource_id=str(body.server_id), details={"count": len(result.get("services") or [])})
    return ok(result)


@router.post("/show", summary="Service status and unit file state")
async def show(body: ServiceQuery, request: Request, user: Reader, db: DbSession) -> dict:
    try:
        unit = normalize_unit(body.unit)
    except ValueError as exc:
        from app.core.responses import ApiError
        raise ApiError(400, "invalid_unit", "Invalid unit name") from exc
    result = await call_agent(db, body.server_id, "services.show", {"unit": unit})
    await record_audit(db, "services.show", request=request, user=user, resource_type="service",
                       resource_id=unit, details={"server_id": str(body.server_id)})
    return ok(result)


@router.post("/logs", summary="Recent journal lines for a service")
async def logs(body: ServiceQuery, request: Request, user: Reader, db: DbSession) -> dict:
    try:
        unit = normalize_unit(body.unit)
    except ValueError as exc:
        from app.core.responses import ApiError
        raise ApiError(400, "invalid_unit", "Invalid unit name") from exc
    result = await call_agent(db, body.server_id, "services.logs", {"unit": unit}, timeout=30)
    await record_audit(db, "services.logs", request=request, user=user, resource_type="service",
                       resource_id=unit, details={"server_id": str(body.server_id), "lines": len(result.get("lines") or [])})
    return ok(result)


@router.post("/operations", status_code=201, summary="Restart, enable or disable a service")
async def operate(body: ServiceChange, request: Request, user: Writer, db: DbSession) -> dict:
    unit = validate_service_action(body.unit, body.action, body.confirm)
    server = await require_server(db, body.server_id)
    job = await begin_job(db, user, "services.apply", server, {"action": body.action, "unit": unit})
    await record_audit(db, f"services.{body.action}", request=request, user=user, resource_type="service",
                       resource_id=unit, details={"server_id": str(server.id), "job_id": str(job.id)})
    return ok(JobOut.model_validate(job).model_dump(mode="json"))
