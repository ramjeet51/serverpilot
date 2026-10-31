"""Browser WebSocket: relays Redis pub/sub events to authenticated clients.

Protocol: client connects, then must send {"type": "auth", "token": "<access token>"} within 5 seconds.
Tokens are never accepted in the URL so they do not end up in proxy or access logs.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.database import get_async_sessionmaker
from app.core.deps import has_permissions, load_user_from_access_token
from app.core.redis import EVENTS_CHANNEL, get_async_redis
from app.core.responses import ApiError

router = APIRouter(tags=["realtime"])
logger = logging.getLogger("serverpilot.ws")

_EVENT_PERMISSIONS = {"job.updated": "jobs:read", "job.log": "jobs:read"}


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    origin = ws.headers.get("origin")
    if origin and origin not in get_settings().cors_origin_list:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Origin not allowed")
        return
    await ws.accept()
    try:
        message = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=5))
        if message.get("type") != "auth" or not isinstance(message.get("token"), str):
            raise ValueError("auth message required")
        async with get_async_sessionmaker()() as db:
            user = await load_user_from_access_token(db, message["token"])
    except (TimeoutError, ValueError, json.JSONDecodeError, ApiError, WebSocketDisconnect):
        await ws.close(code=4401, reason="Unauthorized")
        return

    await ws.send_json({"type": "auth.ok", "payload": {"user_id": str(user.id)}})
    pubsub = get_async_redis().pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)

    async def pump() -> None:
        async for item in pubsub.listen():
            if item.get("type") != "message":
                continue
            try:
                event = json.loads(item["data"])
            except (TypeError, json.JSONDecodeError):
                continue
            required = _EVENT_PERMISSIONS.get(event.get("type"))
            if required and not has_permissions(user, required):
                continue
            await ws.send_text(item["data"])

    async def receive() -> None:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text('{"type":"pong"}')

    tasks = [asyncio.create_task(pump()), asyncio.create_task(receive())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.aclose()
