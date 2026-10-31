"""Send one allowlisted command to a connected agent and wait for its result.

The worker and the API do not open a shell. The gateway already holds the agent
WebSocket and forwards the command. Results and log lines come back on Redis.
"""

import json
import time
import uuid
from collections.abc import Callable

import redis

from app.core.config import get_settings
from app.core.redis import get_sync_redis

CONNECTED_AGENTS_KEY = "sp:gateway:agents"
COMMANDS = "sp:agent:{agent_id}:commands"
RESULTS = "sp:agent:results:{request_id}"
OPERATION_LOCK = "sp:operation:{server_id}"

ALLOWED_ACTIONS = frozenset({
    "software.inspect", "software.versions", "software.apply", "software.library",
    "services.list", "services.show", "services.logs", "services.apply",
})


class AgentOffline(Exception):
    pass


class AgentTimeout(Exception):
    pass


def agent_connected(agent_id: str) -> bool:
    return bool(get_sync_redis().sismember(CONNECTED_AGENTS_KEY, agent_id))


def acquire_operation_lock(server_id: str, owner: str, ttl_seconds: int) -> bool:
    return bool(get_sync_redis().set(OPERATION_LOCK.format(server_id=server_id), owner, nx=True, ex=ttl_seconds))


def release_operation_lock(server_id: str, owner: str) -> None:
    key = OPERATION_LOCK.format(server_id=server_id)
    client = get_sync_redis()
    if client.get(key) == owner:
        client.delete(key)


def dispatch_command(agent_id: str, action: str, params: dict, timeout: float,
                     on_log: Callable[[str], None] | None = None) -> dict:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Action '{action}' is not allowed")
    if not agent_connected(agent_id):
        raise AgentOffline("Agent is not connected")
    request_id = str(uuid.uuid4())
    client = redis.from_url(get_settings().redis_dsn, decode_responses=True, socket_timeout=None)
    pubsub = client.pubsub()
    pubsub.subscribe(RESULTS.format(request_id=request_id))
    try:
        subscribed = False
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            message = pubsub.get_message(timeout=0.2)
            if message and message.get("type") == "subscribe":
                subscribed = True
                break
        if not subscribed:
            raise AgentTimeout("Could not subscribe for the agent result")
        client.publish(COMMANDS.format(agent_id=agent_id), json.dumps({
            "type": "command", "id": request_id, "action": action, "params": params,
        }))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = pubsub.get_message(timeout=1.0)
            if not message or message.get("type") != "message":
                continue
            payload = json.loads(message["data"])
            if payload.get("type") == "log":
                line = str(payload.get("line") or "")[:500]
                if line and on_log:
                    on_log(line)
                continue
            if payload.get("type") == "result":
                return payload
        raise AgentTimeout("Agent did not finish the operation in time")
    finally:
        pubsub.close()
        client.close()
