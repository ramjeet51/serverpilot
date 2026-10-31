"""Real-time events published to Redis pub/sub and relayed to browsers over WebSocket."""

import json
import logging
from typing import Any

from app.core.redis import EVENTS_CHANNEL, get_async_redis, get_sync_redis

logger = logging.getLogger(__name__)


def _encode(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, "payload": payload}, default=str)


def publish_sync(event_type: str, payload: dict[str, Any]) -> None:
    try:
        get_sync_redis().publish(EVENTS_CHANNEL, _encode(event_type, payload))
    except Exception:  # noqa: BLE001
        logger.warning("failed to publish event", extra={"event_type": event_type})


async def publish(event_type: str, payload: dict[str, Any]) -> None:
    try:
        await get_async_redis().publish(EVENTS_CHANNEL, _encode(event_type, payload))
    except Exception:  # noqa: BLE001
        logger.warning("failed to publish event", extra={"event_type": event_type})
