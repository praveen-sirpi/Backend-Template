"""Redis provider. Optional: with REDIS_URL empty the cache is disabled and `enabled` is False."""

import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str | None, *, key_prefix: str = "") -> None:
        self.url = url
        self.key_prefix = key_prefix
        self._client: Redis | None = None

    @property
    def enabled(self) -> bool:
        return self.url is not None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis is not connected (is REDIS_URL set?)")
        return self._client

    async def connect(self) -> None:
        if not self.url:
            logger.info("Redis disabled (REDIS_URL not set)")
            return
        self._client = Redis.from_url(self.url, decode_responses=True)
        await self._client.ping()
        logger.info("Redis connection successful")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis connection closed")

    async def ping(self) -> bool:
        try:
            return bool(await self.client.ping())
        except (RedisError, RuntimeError):
            return False

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"

    async def get_json(self, key: str) -> Any | None:
        raw = await self.client.get(self._key(key))
        return None if raw is None else json.loads(raw)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        await self.client.set(self._key(key), json.dumps(value, default=str), ex=ttl_seconds)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self.client.delete(*(self._key(k) for k in keys))


cache = RedisCache(settings.redis_url, key_prefix="app:")
