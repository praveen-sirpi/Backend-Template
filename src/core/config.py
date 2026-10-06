"""Application settings, loaded from environment variables and the `.env` file."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

_DEFAULT_JWT_SECRET = "change-me-in-production-use-a-long-random-string"

Environment = Literal["development", "staging", "production", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Backend Template"
    app_version: str = "0.1.0"
    environment: Environment = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True

    # --- Logging ---
    log_level: LogLevel = "INFO"
    log_format: Literal["console", "json"] = "console"
    log_file: Path | None = None

    # --- CORS (comma-separated or JSON list) ---
    cors_origins: Annotated[list[str], NoDecode] = []

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # --- Redis (optional: leave empty to disable) ---
    redis_url: str | None = None

    # --- Security ---
    jwt_secret_key: SecretStr = SecretStr(_DEFAULT_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.startswith("["):
            return json.loads(value)
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("redis_url", "log_file", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _check_production_safety(self) -> Self:
        if self.is_production and self.jwt_secret_key.get_secret_value() == _DEFAULT_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set to a strong random value in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
