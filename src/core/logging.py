"""Logging setup: colored console lines for development, JSON lines for production.

Console:  2026-10-06 10:25:25 Backend Template INFO    GET /health -> 200 (1.2ms)  [81d9e1...]
JSON:     {"timestamp": "...", "level": "INFO", "logger": "app.access", "message": "...", ...}

Every record gets the current request id attached (when there is one), so all logs emitted
while handling a request — from middleware, services or providers — can be correlated.
"""

import contextlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import ClassVar, TextIO

from src.core.config import BASE_DIR, Settings
from src.core.context import get_request_id

_RESET = "\x1b[0m"
_GREEN = "\x1b[32m"
_CYAN = "\x1b[36m"
_GREY = "\x1b[90m"

# Attributes every LogRecord has; anything else was passed through `extra=`.
_RESERVED_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime", "request_id"}

_NOISY_LOGGERS = ("asyncio", "httpx", "httpcore", "multipart", "watchfiles")


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every record that reaches a handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


class ConsoleFormatter(logging.Formatter):
    LEVEL_COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\x1b[34m",
        logging.INFO: "\x1b[32m",
        logging.WARNING: "\x1b[33m",
        logging.ERROR: "\x1b[31m",
        logging.CRITICAL: "\x1b[1;31m",
    }

    def __init__(self, app_name: str, *, use_colors: bool) -> None:
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.app_name = app_name
        self.use_colors = use_colors

    def _paint(self, text: str, color: str) -> str:
        return f"{color}{text}{_RESET}" if self.use_colors and color else text

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self._paint(self.formatTime(record, self.datefmt), _GREEN)
        app_name = self._paint(self.app_name, _CYAN)
        level = self._paint(f"{record.levelname:<7}", self.LEVEL_COLORS.get(record.levelno, ""))
        line = f"{timestamp} {app_name} {level} {record.getMessage()}"

        request_id = getattr(record, "request_id", None)
        if request_id:
            line += "  " + self._paint(f"[{request_id}]", _GREY)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        if record.stack_info:
            line += "\n" + self.formatStack(record.stack_info)
        return line


class JsonFormatter(logging.Formatter):
    """One JSON object per line, ready for Loki / ELK / CloudWatch / Datadog."""

    def __init__(self, app_name: str) -> None:
        super().__init__()
        self.app_name = app_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "app": self.app_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        payload.update(
            (key, value)
            for key, value in vars(record).items()
            if key not in _RESERVED_ATTRS and not key.startswith("_")
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(settings: Settings) -> None:
    """Configure the root logger. Safe to call more than once (reload, tests, Alembic)."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, "_app_handler", False)]:
        root.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler(sys.stderr)
    if settings.log_format == "json":
        console.setFormatter(JsonFormatter(settings.app_name))
    else:
        use_colors = _supports_color(sys.stderr)
        console.setFormatter(ConsoleFormatter(settings.app_name, use_colors=use_colors))
    handlers: list[logging.Handler] = [console]

    if settings.log_file:
        log_path = settings.log_file
        if not log_path.is_absolute():
            log_path = BASE_DIR / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter(settings.app_name))
        handlers.append(file_handler)

    for handler in handlers:
        handler.addFilter(RequestIdFilter())
        handler._app_handler = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Requests are logged by RequestContextMiddleware, so drop uvicorn's duplicate access log.
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.propagate = False

    # In JSON mode, route uvicorn's own server logs through our handlers too.
    if settings.log_format == "json":
        uvicorn_logger = logging.getLogger("uvicorn")
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.db_echo else logging.WARNING
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _supports_color(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not (hasattr(stream, "isatty") and stream.isatty()):
        return False
    if os.name == "nt":
        _enable_windows_ansi()
    return True


def _enable_windows_ansi() -> None:
    """Turn on ANSI escape processing for legacy Windows consoles."""
    with contextlib.suppress(Exception):
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-12)  # STD_ERROR_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(
                handle, mode.value | 0x0004
            )  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
