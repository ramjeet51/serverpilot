"""Consistent API envelope: {"success": bool, "data": ..., "meta": ...} / {"success": false, "error": {...}}."""

import logging
import math
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.logging import request_id_ctx

T = TypeVar("T")
logger = logging.getLogger(__name__)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: dict[str, Any] | None = None


class PageEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: list[T]
    meta: PageMeta


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-based page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def meta(self, total: int) -> PageMeta:
        return PageMeta(page=self.page, page_size=self.page_size, total=total, pages=max(1, math.ceil(total / self.page_size)))


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "meta": meta}


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.details = details


def _error(status: int, code: str, message: str, details: Any = None, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "success": False,
            "error": {"code": code, "message": message, "details": details},
            "request_id": request_id_ctx.get(),
        },
        headers=headers,
    )


_STATUS_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
                 409: "conflict", 413: "payload_too_large", 422: "validation_error", 429: "rate_limited"}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status_code, exc.code, str(exc.detail), exc.details, getattr(exc, "headers", None))

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "error")
        return _error(exc.status_code, code, str(exc.detail), headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return _error(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return _error(500, "internal_error", "An unexpected error occurred")
