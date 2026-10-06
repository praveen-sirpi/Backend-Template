"""Render every error in one envelope:

    {"error": {"code": "not_found", "message": "User not found", "details": null,
               "request_id": "81d9e138ff124dffbff50d8923dc600b"}}

Unhandled exceptions are caught by RequestContextMiddleware, which also uses `error_response`.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.context import get_request_id
from src.core.exceptions import AppError
from src.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details, request_id=get_request_id())
    )
    return JSONResponse(
        status_code=status_code, content=body.model_dump(mode="json"), headers=headers
    )


def _log_handled(request: Request, status_code: int, code: str, message: str) -> None:
    level = logging.ERROR if status_code >= 500 else logging.WARNING
    logger.log(
        level,
        "Handled error path=%s code=%s message=%s",
        request.url.path,
        code,
        message,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    _log_handled(request, exc.status_code, exc.code, exc.message)
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Routing errors (404/405) are already visible in the access log, so they aren't logged here.
    try:
        phrase = HTTPStatus(exc.status_code).phrase
    except ValueError:
        phrase = "HTTP error"
    code = phrase.lower().replace(" ", "_").replace("-", "_")
    message = exc.detail if isinstance(exc.detail, str) else phrase
    details = None if isinstance(exc.detail, str) else exc.detail
    if exc.status_code >= 500:
        _log_handled(request, exc.status_code, code, message)
    return error_response(exc.status_code, code, message, details, exc.headers)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"loc": list(err["loc"]), "message": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    _log_handled(request, 422, "validation_error", f"{len(details)} invalid field(s)")
    return error_response(422, "validation_error", "Request validation failed", details)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
