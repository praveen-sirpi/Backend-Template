"""Application entrypoint.

uv run uvicorn src.main:app --reload
"""

from fastapi import FastAPI

from src.core.config import settings
from src.core.exception_handlers import register_exception_handlers
from src.core.lifespan import lifespan
from src.core.logging import setup_logging
from src.middleware import register_middleware
from src.modules.router import api_router, root_router


def create_app() -> FastAPI:
    setup_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    register_middleware(app, settings)
    register_exception_handlers(app)

    app.include_router(root_router)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=settings.debug)
