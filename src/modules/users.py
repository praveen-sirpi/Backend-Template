import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from src.core.exceptions import ForbiddenError
from src.models.user import User
from src.modules.dependencies import CurrentSuperuser, CurrentUser, UserServiceDep
from src.schemas.common import Page
from src.schemas.user import UserRead, UserUpdate
from src.utils.pagination import PageParams

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead], summary="List users (superuser only)")
async def list_users(
    _: CurrentSuperuser, users: UserServiceDep, page: Annotated[PageParams, Query()]
) -> Page[UserRead]:
    return await users.list_users(page)


@router.patch("/me", response_model=UserRead, summary="Update your own profile")
async def update_me(data: UserUpdate, user: CurrentUser, users: UserServiceDep) -> User:
    return await users.update(user, data)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, current: CurrentUser, users: UserServiceDep) -> User:
    if current.id != user_id and not current.is_superuser:
        raise ForbiddenError()
    return await users.get_by_id(user_id)
