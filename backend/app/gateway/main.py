"""Agent Communication Gateway.

Agents connect outbound to /v1/connect. This process forwards allowlisted commands
to the connected agent. It does not accept a shell.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.database import get_async_sessionmaker
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.redis import get_async_redis
from app.core.responses import ok, register_exception_handlers
from app.schemas.agents import AgentReport
from app.services.agent_bus import ALLOWED_ACTIONS
from app.services.agent_link import accept_agent, mark_disconnected, mark_stale_offline, record_heartbeat, register_agent

settings = get_settings()
setup_logging(settings.log_level, settings.log_format, "agent-gateway")
logger = logging.getLogger("serverpilot.gateway")

CONNECTED_AGENTS_KEY = "sp:gateway:agents"
_started_at = time.time()
_MAX_MESSAGE = 1_000_000


async def _sweep() -> None:
    while True:
        await asyncio.sleep(settings.agent_offline_timeout)
        try:
            async with get_async_sessionmaker()() as db:
                await mark_stale_offline(db)
        except Exception:
            logger.exception("offline sweep failed")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("agent gateway starting", extra={"port": settings.agent_gateway_port, "auth_mode": settings.agent_auth_mode})
    task = asyncio.create_task(_sweep())
    yield
    task.cancel()
    await get_async_redis().aclose()


app = FastAPI(title=f"{settings.app_name} Agent Gateway", version="1.0.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)


def _peer(ws: WebSocket) -> str | None:
    return ws.client.host if ws.client else None


def _command_channel(agent_id: str) -> str:
    return f"sp:agent:{agent_id}:commands"


def _result_channel(request_id: str) -> str:
    return f"sp:agent:results:{request_id}"


async def _forward_commands(agent_id: str, ws: WebSocket, stop: asyncio.Event) -> None:
    client = aioredis.from_url(settings.redis_dsn, decode_responses=True, socket_timeout=None)
    pubsub = client.pubsub()
    await pubsub.subscribe(_command_channel(agent_id))
    try:
        while not stop.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message or message.get("type") != "message":
                continue
            try:
                payload = json.loads(message["data"])
            except json.JSONDecodeError:
                continue
            action = payload.get("action")
            request_id = payload.get("id")
            params = payload.get("params")
            if payload.get("type") != "command" or action not in ALLOWED_ACTIONS:
                continue
            if not isinstance(request_id, str) or len(request_id) > 64 or not isinstance(params, dict):
                continue
            await ws.send_json({"type": "command", "id": request_id, "action": action, "params": params})
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("command forwarder stopped")
    finally:
        await pubsub.aclose()
        await client.aclose()


async def _publish_agent_event(message: dict) -> None:
    request_id = message.get("id")
    if not isinstance(request_id, str) or len(request_id) > 64:
        return
    kind = message.get("type")
    if kind == "command_log":
        body = {"type": "log", "line": str(message.get("line") or "")[:500]}
    elif kind == "command_result":
        result = message.get("result")
        body = {
            "type": "result",
            "ok": bool(message.get("ok")),
            "error": message.get("error"),
            "message": str(message.get("message") or "")[:500],
            "exit_code": message.get("exit_code"),
            "result": result if isinstance(result, dict) else {},
        }
    else:
        return
    await get_async_redis().publish(_result_channel(request_id), json.dumps(body))


async def _read(ws: WebSocket) -> dict:
    raw = await asyncio.wait_for(ws.receive_text(), timeout=settings.agent_offline_timeout)
    if len(raw) > _MAX_MESSAGE:
        raise ValueError("Message too large")
    message = json.loads(raw)
    if not isinstance(message, dict):
        raise ValueError("Message must be an object")
    return message


@app.websocket("/v1/connect")
async def connect(ws: WebSocket) -> None:
    await ws.accept()
    agent_id = None
    try:
        first = await _read(ws)
        report = AgentReport.model_validate(first.get("report") or {})
        token = first.get("token")
        if not isinstance(token, str):
            raise PermissionError("Token required")
        async with get_async_sessionmaker()() as db:
            if first.get("type") == "register":
                reply = await register_agent(db, token, report, _peer(ws))
                token = reply["agent_token"]
                agent_id, ready = await accept_agent(db, token, _peer(ws))
                reply["heartbeat_interval"] = ready["heartbeat_interval"]
            elif first.get("type") == "hello":
                agent_id, reply = await accept_agent(db, token, _peer(ws))
            else:
                raise PermissionError("Expected register or hello")
        await ws.send_json(reply)
        await get_async_redis().sadd(CONNECTED_AGENTS_KEY, str(agent_id))
        stop = asyncio.Event()
        forwarder = asyncio.create_task(_forward_commands(str(agent_id), ws, stop))
        try:
            while True:
                message = await _read(ws)
                kind = message.get("type")
                if kind == "heartbeat":
                    if message.get("token") != token:
                        raise PermissionError("Heartbeat rejected")
                    report = AgentReport.model_validate(message.get("report") or {})
                    async with get_async_sessionmaker()() as db:
                        await record_heartbeat(db, token, report)
                    await ws.send_json({"type": "ok"})
                elif kind in ("command_log", "command_result"):
                    await _publish_agent_event(message)
                else:
                    raise PermissionError("Unexpected agent message")
        finally:
            stop.set()
            forwarder.cancel()
    except (PermissionError, ValidationError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
        logger.info("agent connection closed", extra={"reason": exc.__class__.__name__})
        try:
            await ws.close(code=4401)
        except RuntimeError:
            pass
    except WebSocketDisconnect:
        pass
    finally:
        if agent_id is not None:
            await get_async_redis().srem(CONNECTED_AGENTS_KEY, str(agent_id))
            try:
                async with get_async_sessionmaker()() as db:
                    await mark_disconnected(db, agent_id)
            except Exception:
                logger.exception("failed to mark agent disconnected")


@app.get("/health")
async def health() -> dict:
    r = get_async_redis()
    await r.ping()
    return ok({
        "status": "ok",
        "connected_agents": await r.scard(CONNECTED_AGENTS_KEY),
        "auth_mode": settings.agent_auth_mode,
        "heartbeat_interval": settings.agent_heartbeat_interval,
        "offline_timeout": settings.agent_offline_timeout,
        "uptime_seconds": round(time.time() - _started_at),
    })
