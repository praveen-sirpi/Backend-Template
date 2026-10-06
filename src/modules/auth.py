from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from src.models.user import User
from src.modules.dependencies import AuthServiceDep, CurrentUser, UserServiceDep
from src.schemas.auth import Token
from src.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, users: UserServiceDep) -> User:
    return await users.create(data)


@router.post("/login", response_model=Token, summary="Get an access token (OAuth2 password flow)")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], auth: AuthServiceDep
) -> Token:
    # OAuth2 calls the field "username"; we use the email address.
    return await auth.login(form.username, form.password)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> User:
    return user
