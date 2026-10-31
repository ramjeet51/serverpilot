from functools import lru_cache

import redis
import redis.asyncio as aioredis

from app.core.config import get_settings

EVENTS_CHANNEL = "serverpilot:events"


@lru_cache
def get_async_redis() -> aioredis.Redis:
    return aioredis.from_url(get_settings().redis_dsn, decode_responses=True, socket_timeout=5)


@lru_cache
def get_sync_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_dsn, decode_responses=True, socket_timeout=5)
