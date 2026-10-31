import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.core.redis import get_async_redis

logger = logging.getLogger("serverpilot.access")

_RATE_LIMIT_EXEMPT = ("/api/v1/health",)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        logger.info(
            "request",
            extra={"request_id": rid, "method": request.method, "path": request.url.path,
                   "status": response.status_code, "duration_ms": duration_ms, "client_ip": client_ip(request)},
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP limit backed by Redis. Fails open (with a warning) if Redis is unavailable."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(_RATE_LIMIT_EXEMPT) or request.method == "OPTIONS":
            return await call_next(request)
        limit = get_settings().api_rate_limit_per_minute
        window = int(time.time() // 60)
        key = f"sp:rl:api:{client_ip(request)}:{window}"
        try:
            r = get_async_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 61)
        except Exception:  # noqa: BLE001
            logger.warning("rate limiter unavailable; allowing request")
            return await call_next(request)
        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"success": False, "error": {"code": "rate_limited", "message": "Too many requests", "details": None}},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
