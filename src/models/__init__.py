"""Import every model here so `Base.metadata` is complete for Alembic autogenerate."""

from src.db.base import Base
from src.models.user import User

__all__ = ["Base", "User"]
