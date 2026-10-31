import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.responses import ApiError
from app.models import Agent, Server, ServerMetric, ServerStatus, User
from app.schemas.servers import ServerCreate, ServerOut
from app.services.agent_link import issue_registration


def _out(server: Server, metric: ServerMetric | None) -> ServerOut:
    data = ServerOut.model_validate(server)
    data.agent_status = server.agent.status if server.agent else None
    if metric is not None:
        data.cpu_percent = metric.cpu_percent
        data.memory_percent = metric.memory_percent
        data.disk_percent = metric.disk_percent
    return data


async def _latest_metrics(db: AsyncSession, server_ids: list[uuid.UUID]) -> dict[uuid.UUID, ServerMetric]:
    if not server_ids:
        return {}
    latest = (
        select(ServerMetric.server_id, func.max(ServerMetric.id).label("metric_id"))
        .where(ServerMetric.server_id.in_(server_ids))
        .group_by(ServerMetric.server_id)
        .subquery()
    )
    rows = (await db.execute(select(ServerMetric).join(latest, ServerMetric.id == latest.c.metric_id))).scalars()
    return {row.server_id: row for row in rows}


async def list_servers(db: AsyncSession) -> list[ServerOut]:
    servers = list((await db.execute(
        select(Server).options(selectinload(Server.agent)).order_by(Server.name)
    )).scalars())
    metrics = await _latest_metrics(db, [server.id for server in servers])
    return [_out(server, metrics.get(server.id)) for server in servers]


async def get_server(db: AsyncSession, server_id: uuid.UUID) -> Server:
    server = (await db.execute(
        select(Server).options(selectinload(Server.agent)).where(Server.id == server_id)
    )).scalar_one_or_none()
    if server is None:
        raise ApiError(404, "not_found", "Server not found")
    return server


async def create_server(db: AsyncSession, body: ServerCreate, user: User) -> tuple[ServerOut, str]:
    taken = (await db.execute(select(Server.id).where(func.lower(Server.name) == body.name.lower()))).first()
    if taken:
        raise ApiError(409, "conflict", "A server with this name already exists")
    server = Server(
        name=body.name,
        hostname=body.hostname,
        ip_address=body.ip_address,
        environment=body.environment,
        description=body.description,
        status=ServerStatus.pending,
        created_by_id=user.id,
    )
    db.add(server)
    await db.flush()
    agent = Agent(server_id=server.id, agent_uid=uuid.uuid4().hex, auth_mode="test_token", capabilities={})
    token = issue_registration(agent)
    db.add(agent)
    await db.commit()
    await db.refresh(server)
    server.agent = agent
    return _out(server, None), token


async def rotate_registration(db: AsyncSession, server_id: uuid.UUID) -> tuple[ServerOut, str]:
    server = await get_server(db, server_id)
    if server.agent is None:
        raise ApiError(409, "invalid_state", "This server has no agent record")
    token = issue_registration(server.agent)
    server.status = ServerStatus.pending
    await db.commit()
    await db.refresh(server)
    return _out(server, None), token


async def delete_server(db: AsyncSession, server_id: uuid.UUID) -> None:
    server = await get_server(db, server_id)
    await db.delete(server)
    await db.commit()
