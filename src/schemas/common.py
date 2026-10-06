from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field


def _as_utc(value: datetime) -> datetime:
    # Some databases (SQLite) drop the timezone; values are always stored as UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]


class ErrorDetail(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["User not found"])
    details: Any | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
