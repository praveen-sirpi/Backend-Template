from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.common import Page


class PageParams(BaseModel):
    """Use in routes as `Annotated[PageParams, Query()]`."""

    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of items to return")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


async def paginate[T: BaseModel](
    session: AsyncSession, stmt: Select[Any], params: PageParams, schema: type[T]
) -> Page[T]:
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = await session.scalars(stmt.limit(params.limit).offset(params.offset))
    return Page[schema](  # type: ignore[valid-type]
        items=[schema.model_validate(row) for row in rows],
        total=total or 0,
        limit=params.limit,
        offset=params.offset,
    )
