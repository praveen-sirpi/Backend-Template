"""Startup and shutdown orchestration. Each dependency logs its own status."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import settings
from src.db.session import db
from src.providers.cache import cache

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting %s v%s (%s)...", settings.app_name, settings.app_version, settings.environment
    )

    logger.info("Initializing database connection...")
    try:
        await db.ping()
    except Exception as exc:
        logger.critical("Database connection failed (%s): %s", db.display_url, exc)
        raise
    logger.info("Database connection successful (%s)", db.display_url)

    try:
        await cache.connect()
    except Exception as exc:
        logger.critical("Redis connection failed: %s", exc)
        await db.dispose()
        raise

    logger.info("%s started successfully", settings.app_name)
    try:
        yield
    finally:
        logger.info("Shutting down %s...", settings.app_name)
        await cache.close()
        await db.dispose()
        logger.info("Database connection closed")
        logger.info("Shutdown complete")
