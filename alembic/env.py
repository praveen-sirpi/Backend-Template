"""Alembic environment: async engine, URL and logging taken from the application settings."""

import asyncio
import logging

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import settings
from src.core.logging import setup_logging
from src.models import Base  # importing src.models registers every model on Base.metadata

config = context.config
target_metadata = Base.metadata

if config.attributes.get("configure_logging", True):
    setup_logging(settings)
    logging.getLogger("alembic").setLevel(logging.INFO)
    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)


def _configure(**kwargs: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite can't ALTER most things in place; batch mode recreates the table instead.
        render_as_batch=settings.is_sqlite,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: emit SQL to stdout without connecting."""
    _configure(url=settings.database_url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    # A connection can be passed in programmatically: config.attributes["connection"] = conn
    connection = config.attributes.get("connection")
    if connection is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
