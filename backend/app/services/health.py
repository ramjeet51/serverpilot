import asyncio
import time
from typing import Any

import httpx
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_async_engine
from app.core.redis import get_async_redis
from app.worker.celery_app import celery_app


async def _timed(coro) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        details = await asyncio.wait_for(coro, timeout=5)
        return {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 2), **(details or {})}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": f"{exc.__class__.__name__}: {str(exc)[:200]}"}


async def _postgres() -> dict[str, Any]:
    async with get_async_engine().connect() as conn:
        version = (await conn.execute(text("SHOW server_version"))).scalar_one()
        revision = None
        try:
            revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        except Exception:
            await conn.rollback()
    return {"version": version, "migration": revision}


async def _redis() -> dict[str, Any]:
    r = get_async_redis()
    await r.ping()
    info = await r.info("server")
    return {"version": info.get("redis_version")}


async def _worker() -> dict[str, Any]:
    replies = await run_in_threadpool(celery_app.control.ping, timeout=1.5)
    if not replies:
        raise RuntimeError("No Celery workers responded")
    return {"workers": sorted(name for reply in replies for name in reply)}


async def _gateway() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=3) as client:
        resp = await client.get(f"{get_settings().gateway_base_url}/health")
        resp.raise_for_status()
        body = resp.json()
    return {"connected_agents": body.get("data", {}).get("connected_agents", 0)}


async def platform_health() -> dict[str, Any]:
    postgres, redis, worker, gateway = await asyncio.gather(
        _timed(_postgres()), _timed(_redis()), _timed(_worker()), _timed(_gateway())
    )
    components = {"api": {"status": "ok"}, "postgres": postgres, "redis": redis, "worker": worker, "gateway": gateway}
    critical_ok = postgres["status"] == "ok" and redis["status"] == "ok"
    all_ok = all(c["status"] == "ok" for c in components.values())
    return {"status": "ok" if all_ok else ("degraded" if critical_ok else "down"), "components": components}
