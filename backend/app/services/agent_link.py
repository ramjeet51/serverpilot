"""Registration tokens and heartbeat updates shared by the API and the agent gateway."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import Agent, AgentStatus, Server, ServerMetric, ServerStatus
from app.schemas.agents import AgentReport

TOKEN_PREFIX = "spagent_"


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _matches(token: str, digest: str | None) -> bool:
    if not digest:
        return False
    return hmac.compare_digest(hash_token(token), digest)


async def _load(db: AsyncSession, token: str) -> Agent | None:
    digest = hash_token(token)
    agent = (await db.execute(
        select(Agent).options(selectinload(Agent.server)).where(Agent.registration_token_hash == digest)
    )).scalar_one_or_none()
    if agent is None or agent.status == AgentStatus.revoked:
        return None
    if not _matches(token, agent.registration_token_hash):
        return None
    if agent.registration_expires_at is not None and agent.registration_expires_at < datetime.now(UTC):
        return None
    return agent


def _apply_report(server: Server, agent: Agent, report: AgentReport) -> ServerMetric:
    now = datetime.now(UTC)
    server.hostname = report.hostname or server.hostname
    server.os_name = report.os_name
    server.os_version = report.os_version
    server.kernel_version = report.kernel_version
    server.cpu_cores = report.cpu_cores
    server.memory_total_bytes = report.memory_total_bytes or server.memory_total_bytes
    server.disk_total_bytes = report.disk_total_bytes or server.disk_total_bytes
    server.status = ServerStatus.online
    server.last_seen_at = now
    agent.status = AgentStatus.connected
    agent.last_heartbeat_at = now
    agent.version = report.version or agent.version
    db_metric = ServerMetric(
        server_id=server.id,
        collected_at=now,
        cpu_percent=report.cpu_percent,
        memory_percent=report.memory_percent,
        memory_used_bytes=report.memory_used_bytes,
        disk_percent=report.disk_percent,
        net_rx_bytes=report.net_rx_bytes,
        net_tx_bytes=report.net_tx_bytes,
        load_1=report.load_1,
        load_5=report.load_5,
        load_15=report.load_15,
        process_count=report.process_count,
    )
    return db_metric


async def register_agent(db: AsyncSession, token: str, report: AgentReport, remote_ip: str | None) -> dict:
    agent = await _load(db, token)
    if agent is None or agent.registration_expires_at is None:
        raise PermissionError("Registration token is invalid or already used")
    permanent = new_token()
    agent.registration_token_hash = hash_token(permanent)
    agent.registration_expires_at = None
    agent.registered_at = datetime.now(UTC)
    agent.auth_mode = "test_token"
    agent.remote_ip = remote_ip
    metric = _apply_report(agent.server, agent, report)
    db.add(metric)
    await db.commit()
    return {
        "type": "registered",
        "agent_token": permanent,
        "server_id": str(agent.server_id),
        "heartbeat_interval": get_settings().agent_heartbeat_interval,
    }


async def accept_agent(db: AsyncSession, token: str, remote_ip: str | None) -> tuple[uuid.UUID, dict]:
    agent = await _load(db, token)
    if agent is None or agent.registered_at is None or agent.registration_expires_at is not None:
        raise PermissionError("Agent token is invalid")
    agent.remote_ip = remote_ip
    agent.status = AgentStatus.connected
    agent.server.status = ServerStatus.online
    await db.commit()
    return agent.id, {"type": "ready", "heartbeat_interval": get_settings().agent_heartbeat_interval}


async def record_heartbeat(db: AsyncSession, token: str, report: AgentReport) -> None:
    agent = await _load(db, token)
    if agent is None or agent.registered_at is None:
        raise PermissionError("Agent token is invalid")
    db.add(_apply_report(agent.server, agent, report))
    await db.commit()


async def mark_disconnected(db: AsyncSession, agent_id: uuid.UUID) -> None:
    agent = (await db.execute(
        select(Agent).options(selectinload(Agent.server)).where(Agent.id == agent_id)
    )).scalar_one_or_none()
    if agent is None or agent.status == AgentStatus.revoked:
        return
    agent.status = AgentStatus.disconnected
    agent.server.status = ServerStatus.offline
    await db.commit()


async def mark_stale_offline(db: AsyncSession) -> None:
    cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().agent_offline_timeout)
    rows = (await db.execute(
        select(Agent).options(selectinload(Agent.server)).where(Agent.status == AgentStatus.connected)
    )).scalars()
    changed = False
    for agent in rows:
        seen = agent.last_heartbeat_at
        if seen is None or seen < cutoff:
            agent.status = AgentStatus.disconnected
            agent.server.status = ServerStatus.offline
            changed = True
    if changed:
        await db.commit()


def issue_registration(agent: Agent) -> str:
    token = new_token()
    agent.registration_token_hash = hash_token(token)
    agent.registration_expires_at = datetime.now(UTC) + timedelta(hours=get_settings().agent_registration_ttl_hours)
    agent.registered_at = None
    agent.status = AgentStatus.pending
    return token
