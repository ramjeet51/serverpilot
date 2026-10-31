import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import get_async_engine
from app.core.logging import setup_logging
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.core.redis import get_async_redis
from app.core.responses import register_exception_handlers

settings = get_settings()
setup_logging(settings.log_level, settings.log_format, "backend")
logger = logging.getLogger("serverpilot")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("backend starting", extra={"env": settings.app_env, "port": settings.backend_port})
    yield
    await get_async_redis().aclose()
    await get_async_engine().dispose()
    logger.info("backend stopped")


def create_app() -> FastAPI:
    docs = settings.api_docs_enabled
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="1.0.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url="/api/redoc" if docs else None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
