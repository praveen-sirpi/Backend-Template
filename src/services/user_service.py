import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictError, NotFoundError
from src.core.security import hash_password
from src.models.user import User
from src.schemas.common import Page
from src.schemas.user import UserCreate, UserRead, UserUpdate
from src.utils.pagination import PageParams, paginate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email.lower()))

    async def list_users(self, params: PageParams) -> Page[UserRead]:
        stmt = select(User).order_by(User.created_at.desc(), User.id)
        return await paginate(self.session, stmt, params, UserRead)

    async def create(self, data: UserCreate, *, is_superuser: bool = False) -> User:
        if await self.get_by_email(data.email) is not None:
            raise ConflictError("A user with this email already exists", code="email_taken")

        user = User(
            email=data.email.lower(),
            hashed_password=await hash_password(data.password),
            full_name=data.full_name,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:  # lost a race with a concurrent signup
            await self.session.rollback()
            raise ConflictError(
                "A user with this email already exists", code="email_taken"
            ) from exc

        logger.info("User created id=%s superuser=%s", user.id, is_superuser)
        return user

    async def update(self, user: User, data: UserUpdate) -> User:
        changes = data.model_dump(exclude_unset=True)
        password = changes.pop("password", None)
        if password:
            user.hashed_password = await hash_password(password)
        for field, value in changes.items():
            setattr(user, field, value)

        await self.session.commit()
        logger.info("User updated id=%s fields=%s", user.id, sorted(data.model_fields_set))
        return user
