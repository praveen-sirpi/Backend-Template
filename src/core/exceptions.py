"""Domain exceptions. Raise these from services/routes; they're rendered as the error envelope.

raise NotFoundError("User not found")
raise ConflictError("Email already registered", code="email_taken")
"""

from typing import Any


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        self.headers = headers or self.headers
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Not authenticated"
    headers = {"WWW-Authenticate": "Bearer"}  # noqa: RUF012


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource already exists"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Service temporarily unavailable"
