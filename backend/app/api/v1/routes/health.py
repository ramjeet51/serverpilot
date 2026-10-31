from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.responses import ok
from app.services.health import platform_health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def live() -> dict:
    return ok({"status": "ok"})


@router.get("", summary="Full platform health (PostgreSQL, Redis, Celery, agent gateway)")
async def health() -> JSONResponse:
    s = get_settings()
    report = await platform_health()
    report.update({"app": s.app_name, "environment": s.app_env})
    return JSONResponse(status_code=200 if report["status"] != "down" else 503, content=ok(report))
