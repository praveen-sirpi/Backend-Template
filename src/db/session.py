"""Async engine, session factory and the per-request session dependency."""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import Settings, settings


class Database:
    def __init__(self, url: str, **engine_options: Any) -> None:
        self.url = make_url(url)
        self.engine = create_async_engine(url, pool_pre_ping=True, **engine_options)
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )

    @property
    def display_url(self) -> str:
        return self.url.render_as_string(hide_password=True)

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


def _engine_options(settings: Settings) -> dict[str, Any]:
    if settings.is_sqlite:
        return {}
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
    }


db = Database(settings.database_url, **_engine_options(settings))


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """One session per request. Services commit explicitly; anything uncommitted is rolled back."""
    async with db.session_factory() as session:
        yield session
