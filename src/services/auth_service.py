import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import burn_password_check, create_access_token, verify_password
from src.models.user import User
from src.schemas.auth import Token
from src.services.user_service import UserService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserService(session)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if user is None:
            await burn_password_check(password)
            raise UnauthorizedError("Incorrect email or password", code="invalid_credentials")
        if not await verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password", code="invalid_credentials")
        if not user.is_active:
            raise ForbiddenError("This account has been disabled", code="inactive_user")
        return user

    async def login(self, email: str, password: str) -> Token:
        user = await self.authenticate(email, password)
        logger.info("User signed in id=%s", user.id)
        return Token(
            access_token=create_access_token(str(user.id)),
            expires_in=settings.access_token_expire_minutes * 60,
        )
