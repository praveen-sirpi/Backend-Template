import os
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest

# Configure the app for tests BEFORE anything from `src` is imported (settings load on import).
_TEST_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}",
        "REDIS_URL": "",
        "LOG_LEVEL": "WARNING",
        "LOG_FILE": "",
        "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256-signing",
    }
)

from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from src.core.config import BASE_DIR, settings
from src.db.session import db
from src.main import app
from src.models import Base, User
from src.schemas.user import UserCreate
from src.services.user_service import UserService

API = settings.api_prefix
PASSWORD = "correct-horse-battery"

UserFactory = Callable[..., Awaitable[User]]


@pytest.fixture(scope="session", autouse=True)
def _migrate_database() -> None:
    """Build the schema with the real Alembic migrations, so migrations are tested too."""
    command.upgrade(Config(str(BASE_DIR / "alembic.ini")), "head")


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    yield
    async with db.engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await db.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
def create_user() -> UserFactory:
    async def _create(
        email: str = "user@example.com", password: str = PASSWORD, *, is_superuser: bool = False
    ) -> User:
        async with db.session_factory() as session:
            return await UserService(session).create(
                UserCreate(email=email, password=password), is_superuser=is_superuser
            )

    return _create


async def auth_headers(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = await client.post(
        f"{API}/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
