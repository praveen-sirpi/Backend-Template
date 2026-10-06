from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.core.config import Settings
from src.middleware.request_context import RequestContextMiddleware


def register_middleware(app: FastAPI, settings: Settings) -> None:
    """The last middleware added is the outermost.

    CORS is outermost so that every response, including the JSON 500 produced by
    RequestContextMiddleware, carries CORS headers.
    """
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
