"""Password hashing (Argon2) and JWT access tokens."""

import uuid
from datetime import timedelta
from functools import cache
from typing import Any

import jwt
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from src.core.config import settings
from src.core.exceptions import UnauthorizedError
from src.utils.time import utcnow

_password_hash = PasswordHash.recommended()


# Hashing is CPU-bound (tens of ms), so it runs in a worker thread to keep the event loop free.
async def hash_password(password: str) -> str:
    return await run_in_threadpool(_password_hash.hash, password)


async def verify_password(password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(_password_hash.verify, password, hashed_password)


@cache
def _dummy_hash() -> str:
    return _password_hash.hash(uuid.uuid4().hex)


def _verify_against_dummy(password: str) -> None:
    _password_hash.verify(password, _dummy_hash())


async def burn_password_check(password: str) -> None:
    """Spend the same time as a real check so login timing doesn't reveal unknown emails."""
    await run_in_threadpool(_verify_against_dummy, password)


def create_access_token(subject: str, *, expires_delta: timedelta | None = None) -> str:
    now = utcnow()
    expires = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expires,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token", code="invalid_token") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type", code="invalid_token")
    return payload
