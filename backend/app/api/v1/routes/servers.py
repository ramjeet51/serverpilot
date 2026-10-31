import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.deps import DbSession, require_permissions
from app.core.responses import ok
from app.models import User
from app.schemas.servers import ServerCreate
from app.services import servers as server_service
from app.services.audit import record_audit

router = APIRouter(prefix="/servers", tags=["servers"])

Reader = Annotated[User, Depends(require_permissions("servers:read"))]
Writer = Annotated[User, Depends(require_permissions("servers:write"))]


@router.get("", summary="List managed servers")
async def list_servers(_: Reader, db: DbSession) -> dict:
    rows = await server_service.list_servers(db)
    return ok([row.model_dump(mode="json") for row in rows])


@router.post("", status_code=201, summary="Add a server and issue a one-time agent registration token")
async def create_server(body: ServerCreate, request: Request, user: Writer, db: DbSession) -> dict:
    server, token = await server_service.create_server(db, body, user)
    await record_audit(db, "servers.create", request=request, user=user, resource_type="server",
                       resource_id=str(server.id), details={"name": server.name, "ip_address": server.ip_address})
    fresh = await server_service.get_server(db, server.id)
    payload = {
        "server": server.model_dump(mode="json"),
        "registration_token": token,
        "gateway_url": get_settings().agent_ws_url,
        "expires_at": fresh.agent.registration_expires_at.isoformat() if fresh.agent and fresh.agent.registration_expires_at else None,
    }
    return ok(payload)


@router.get("/{server_id}", summary="Get one server")
async def get_server(server_id: uuid.UUID, _: Reader, db: DbSession) -> dict:
    server = await server_service.get_server(db, server_id)
    rows = await server_service.list_servers(db)
    match = next((row for row in rows if row.id == server.id), None)
    return ok(match.model_dump(mode="json") if match else {})


@router.post("/{server_id}/registration-token", summary="Replace the agent token. The previous token stops working.")
async def rotate_token(server_id: uuid.UUID, request: Request, user: Writer, db: DbSession) -> dict:
    server, token = await server_service.rotate_registration(db, server_id)
    fresh = await server_service.get_server(db, server.id)
    await record_audit(db, "servers.rotate_token", request=request, user=user, resource_type="server",
                       resource_id=str(server.id))
    return ok({
        "server": server.model_dump(mode="json"),
        "registration_token": token,
        "gateway_url": get_settings().agent_ws_url,
        "expires_at": fresh.agent.registration_expires_at.isoformat() if fresh.agent and fresh.agent.registration_expires_at else None,
    })


@router.delete("/{server_id}", summary="Remove a server and its agent")
async def delete_server(server_id: uuid.UUID, request: Request, user: Writer, db: DbSession) -> dict:
    await server_service.delete_server(db, server_id)
    await record_audit(db, "servers.delete", request=request, user=user, resource_type="server", resource_id=str(server_id))
    return ok({"deleted": True})
