"""Shared FastAPI dependencies. Use the `Annotated` aliases in route signatures:

async def handler(user: CurrentUser, users: UserServiceDep): ...
"""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import decode_access_token
from src.db.session import get_db_session
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.user_service import UserService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

# auto_error=False so a missing token goes through our error envelope instead of FastAPI's.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login", auto_error=False)


def get_user_service(session: DbSession) -> UserService:
    return UserService(session)


def get_auth_service(session: DbSession) -> AuthService:
    return AuthService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    session: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    if not token:
        raise UnauthorizedError("Not signed in")

    payload = decode_access_token(token)
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise UnauthorizedError("Invalid token", code="invalid_token") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive", code="invalid_token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise ForbiddenError()
    return user


CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
