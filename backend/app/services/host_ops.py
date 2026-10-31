"""Software and service operations for one managed server."""

import re
import uuid
from datetime import UTC, datetime

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.responses import ApiError
from app.models import Agent, AgentStatus, Server, ServiceInventory, SoftwareInventory, User
from app.services.agent_bus import AgentOffline, AgentTimeout, acquire_operation_lock, agent_connected, dispatch_command
from app.services.catalogue import (
    CATALOGUE, PACKAGE_ACTIONS, PROTECTED_SERVICE_ACTIONS, PROTECTED_UNITS, SERVICE_ACTIONS, SoftwareSpec,
    normalize_unit,
)
from app.services.jobs import create_job

_VERSION = re.compile(r"^[0-9][A-Za-z0-9.+:~_-]{0,80}$")
_AGENT_ERRORS = {
    "apt_locked": 409,
    "helper_missing": 409,
    "busy": 409,
    "protected_package": 400,
    "protected_service": 400,
    "invalid_version": 400,
    "invalid_unit": 400,
    "invalid_request": 400,
    "archive_failed": 502,
    "timeout": 504,
}


async def require_server(db: AsyncSession, server_id: uuid.UUID) -> Server:
    server = await db.get(Server, server_id)
    if server is None:
        raise ApiError(404, "not_found", "Server not found")
    return server


async def _agent_id(db: AsyncSession, server_id: uuid.UUID) -> str:
    await require_server(db, server_id)
    agent = (await db.execute(select(Agent).where(Agent.server_id == server_id))).scalar_one_or_none()
    if agent is None or agent.status != AgentStatus.connected or not agent_connected(str(agent.id)):
        raise ApiError(409, "agent_offline", "The agent on this server is not connected")
    return str(agent.id)


def _raise_agent_error(payload: dict) -> None:
    if payload.get("ok"):
        return
    code = str(payload.get("error") or "operation_failed")
    message = str(payload.get("message") or "The operation failed")
    raise ApiError(_AGENT_ERRORS.get(code, 502), code, message, {"exit_code": payload.get("exit_code")})


async def call_agent(db: AsyncSession, server_id: uuid.UUID, action: str, params: dict, timeout: float = 25) -> dict:
    agent_id = await _agent_id(db, server_id)
    try:
        payload = await run_in_threadpool(dispatch_command, agent_id, action, params, timeout)
    except AgentOffline as exc:
        raise ApiError(409, "agent_offline", "The agent on this server is not connected") from exc
    except AgentTimeout as exc:
        raise ApiError(504, "agent_timeout", "The agent did not answer in time") from exc
    _raise_agent_error(payload)
    result = payload.get("result") or {}
    result["exit_code"] = payload.get("exit_code", 0)
    return result


def _spec(software_id: str) -> SoftwareSpec:
    spec = CATALOGUE.get(software_id)
    if spec is None:
        raise ApiError(400, "unknown_software", "That software is not in the catalogue")
    return spec


def validate_change(software_id: str, action: str, version: str | None, confirm: bool) -> SoftwareSpec:
    if action not in PACKAGE_ACTIONS:
        raise ApiError(400, "invalid_request", "Unknown package action")
    spec = _spec(software_id)
    if action == "remove" and spec.protected_remove:
        raise ApiError(400, "protected_package", f"{spec.name} is part of the system and cannot be removed")
    if action in ("remove", "update") and not confirm:
        raise ApiError(400, "confirmation_required", "Confirm this package change before it runs")
    if version:
        if action != "install" or not _VERSION.match(version):
            raise ApiError(400, "invalid_version", "Version is not a valid package version")
    return spec


def validate_service_action(unit: str, action: str, confirm: bool) -> str:
    if action not in SERVICE_ACTIONS:
        raise ApiError(400, "invalid_request", "Unknown service action")
    try:
        name = normalize_unit(unit)
    except ValueError as exc:
        raise ApiError(400, "invalid_unit", "Invalid unit name") from exc
    if name in PROTECTED_UNITS and action in PROTECTED_SERVICE_ACTIONS:
        raise ApiError(400, "protected_service", f"{name} cannot be disabled from ServerPilot")
    if action in ("restart", "disable") and not confirm:
        raise ApiError(400, "confirmation_required", "Confirm this service change before it runs")
    return name


async def begin_job(db: AsyncSession, user: User, job_type: str, server: Server, args: dict):
    from app.services.jobs import JOB_DEFINITIONS

    owner = str(uuid.uuid4())
    timeout = JOB_DEFINITIONS[job_type].timeout_seconds
    if not acquire_operation_lock(str(server.id), owner, timeout + 30):
        raise ApiError(409, "operation_in_progress", "Another package or service operation is already running on this server")
    try:
        return await create_job(db, job_type, {"server_id": str(server.id), "lock_owner": owner, "args": args},
                                user, server_id=server.id)
    except Exception:
        from app.services.agent_bus import release_operation_lock
        release_operation_lock(str(server.id), owner)
        raise


async def save_software(db: AsyncSession, server_id: uuid.UUID, packages: list[dict]) -> None:
    now = datetime.now(UTC)
    for item in packages:
        software_id = item.get("id")
        if software_id not in CATALOGUE:
            continue
        row = (await db.execute(select(SoftwareInventory).where(
            SoftwareInventory.server_id == server_id, SoftwareInventory.package_name == software_id,
        ))).scalar_one_or_none()
        if row is None:
            row = SoftwareInventory(server_id=server_id, package_name=software_id, source="apt")
            db.add(row)
        installed = bool(item.get("installed"))
        row.status = "installed" if installed else "absent"
        row.version = item.get("version")
        row.candidate_version = item.get("candidate")
        row.installed_at = now if installed else None
    await db.commit()


async def save_services(db: AsyncSession, server_id: uuid.UUID, services: list[dict]) -> None:
    await db.execute(delete(ServiceInventory).where(ServiceInventory.server_id == server_id))
    for item in services:
        unit = str(item.get("unit") or "")
        if not unit:
            continue
        db.add(ServiceInventory(
            server_id=server_id, unit_name=unit[:128], description=str(item.get("description") or "")[:255],
            active_state=str(item.get("active") or "unknown")[:32], sub_state=str(item.get("sub") or "unknown")[:32],
            unit_file_state=str(item.get("enabled") or "unknown")[:32],
        ))
    await db.commit()


def save_software_sync(session: Session, server_id: uuid.UUID, packages: list[dict]) -> None:
    now = datetime.now(UTC)
    for item in packages:
        software_id = item.get("id")
        if software_id not in CATALOGUE:
            continue
        row = session.execute(select(SoftwareInventory).where(
            SoftwareInventory.server_id == server_id, SoftwareInventory.package_name == software_id,
        )).scalar_one_or_none()
        if row is None:
            row = SoftwareInventory(server_id=server_id, package_name=software_id, source="apt")
            session.add(row)
        installed = bool(item.get("installed"))
        row.status = "installed" if installed else "absent"
        row.version = item.get("version")
        row.candidate_version = item.get("candidate")
        row.installed_at = now if installed else None
    session.commit()
