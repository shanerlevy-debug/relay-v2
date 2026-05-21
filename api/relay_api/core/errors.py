"""Global exception handlers + request-logging middleware.

Adapted from Powerloom's core/errors.py — same JSON error envelope shape so
clients can branch on `error.code`. Removed Powerloom's RBAC contextvar
reset (we don't have RBAC at this scope).
"""
from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from relay_api.core.logging import get_logger

log = get_logger(__name__)


def _error_payload(
    status: int,
    code: str,
    message: str,
    details: object = None,
) -> dict:
    """Canonical error envelope. Keep stable — clients key on it."""
    body: dict = {"error": {"code": code, "message": message, "status": status}}
    if details is not None:
        body["error"]["details"] = details
    return body


async def _http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    log.warning(
        "http_exception",
        path=request.url.path,
        status=exc.status_code,
        detail=exc.detail,
    )
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        code = str(exc.detail.get("code") or "http_error")
        message = str(exc.detail.get("message") or "")
        details = {
            k: v for k, v in exc.detail.items() if k not in ("code", "message")
        } or None
        body = _error_payload(exc.status_code, code, message, details)
        body["detail"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=body)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.status_code, "http_error", str(exc.detail)),
    )


async def _validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    from fastapi.encoders import jsonable_encoder

    errors = jsonable_encoder(exc.errors())
    log.warning("validation_error", path=request.url.path, errors=errors)
    return JSONResponse(
        status_code=422,
        content=_error_payload(422, "validation_error", "Invalid request", errors),
    )


async def _unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    log.error(
        "unhandled_exception",
        path=request.url.path,
        exc_type=type(exc).__name__,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=_error_payload(500, "internal_error", "Internal server error"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


def _new_request_id() -> str:
    return uuid.uuid4().hex


async def request_logging_middleware(request: Request, call_next):
    """Attach a request_id, log the request, time it, emit a response log line.

    Uses structlog's contextvars so downstream log calls in the same request
    carry the request_id automatically.
    """
    request_id = request.headers.get("x-request-id", _new_request_id())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.error("request_failed", duration_ms=round(elapsed_ms, 2))
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info("request", status=response.status_code, duration_ms=round(elapsed_ms, 2))
    response.headers["x-request-id"] = request_id
    return response
