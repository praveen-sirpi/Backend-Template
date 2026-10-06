"""Create a superuser, or promote an existing user.

uv run python -m scripts.create_superuser --email admin@example.com
uv run python -m scripts.create_superuser --email admin@example.com --password "s3cret-pass"
"""

import argparse
import asyncio
import getpass
import logging
import sys

from pydantic import ValidationError

from src.core.config import settings
from src.core.logging import setup_logging
from src.db.session import db
from src.schemas.user import UserCreate
from src.services.user_service import UserService

logger = logging.getLogger("scripts.create_superuser")


async def create_superuser(email: str, password: str | None, full_name: str | None) -> int:
    try:
        async with db.session_factory() as session:
            users = UserService(session)
            existing = await users.get_by_email(email)

            if existing is not None:
                if existing.is_superuser:
                    logger.info("User %s is already a superuser", email)
                else:
                    existing.is_superuser = True
                    await session.commit()
                    logger.info("Promoted existing user %s to superuser", email)
                return 0

            password = password or getpass.getpass("Password: ")
            try:
                data = UserCreate(email=email, password=password, full_name=full_name)
            except ValidationError as exc:
                for error in exc.errors():
                    logger.error("%s: %s", ".".join(map(str, error["loc"])), error["msg"])
                return 1

            user = await users.create(data, is_superuser=True)
            logger.info("Superuser created: %s (id=%s)", user.email, user.id)
            return 0
    finally:
        await db.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="Prompted for if omitted")
    parser.add_argument("--full-name")
    args = parser.parse_args()

    setup_logging(settings)
    sys.exit(asyncio.run(create_superuser(args.email, args.password, args.full_name)))


if __name__ == "__main__":
    main()
