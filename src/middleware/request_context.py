"""Pure ASGI middleware that, for every HTTP request:

- assigns a request id (reuses a valid incoming `X-Request-ID`) and returns it in the response
- makes the id available to every log line via a context variable
- writes one access log line: `GET /path -> 200 (12.3ms)`
- turns unhandled exceptions into a logged traceback plus a JSON 500 response

It's pure ASGI (not BaseHTTPMiddleware), so it doesn't buffer streaming responses or break
context variables.
"""

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.context import request_id_ctx
from src.core.exception_handlers import error_response

# A dedicated logger name makes access logs easy to filter or route separately.
access_logger = logging.getLogger("app.access")
logger = logging.getLogger(__name__)

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestContextMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        header_name: str = "X-Request-ID",
        quiet_paths: frozenset[str] = frozenset({"/health"}),
    ) -> None:
        self.app = app
        self.header_name = header_name
        self.header_key = header_name.lower().encode("latin-1")
        self.quiet_paths = quiet_paths  # logged at DEBUG, e.g. load-balancer probes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._incoming_request_id(scope) or uuid.uuid4().hex
        # Not reset on purpose: each request runs in its own task/context, and keeping it set
        # lets anything logged after this middleware returns still carry the id.
        request_id_ctx.set(request_id)

        method: str = scope["method"]
        path: str = scope["path"]
        status_code = 500
        response_started = False
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message).append(self.header_name, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("Unhandled error path=%s", path)
            if response_started:
                raise
            response = error_response(500, "internal_error", "Internal server error")
            await response(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            if status_code >= 500:
                level = logging.ERROR
            elif path in self.quiet_paths:
                level = logging.DEBUG
            else:
                level = logging.INFO
            access_logger.log(
                level,
                "%s %s -> %d (%.1fms)",
                method,
                path,
                status_code,
                duration_ms,
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )

    def _incoming_request_id(self, scope: Scope) -> str | None:
        for key, value in scope["headers"]:
            if key == self.header_key:
                candidate = value.decode("latin-1")
                return candidate if _VALID_REQUEST_ID.match(candidate) else None
        return None
