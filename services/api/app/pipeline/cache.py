import time
from typing import Protocol

from redis.asyncio import Redis


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_s: int) -> None: ...


class RedisCache:
    def __init__(self, redis: Redis, prefix: str = "buylens:cache:") -> None:
        self._redis = redis
        self._prefix = prefix

    async def get(self, key: str) -> str | None:
        value = await self._redis.get(self._prefix + key)
        return value.decode() if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, ttl_s: int) -> None:
        await self._redis.set(self._prefix + key, value, ex=ttl_s)


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        hit = self._data.get(key)
        if hit is None or hit[0] < time.monotonic():
            return None
        return hit[1]

    async def set(self, key: str, value: str, ttl_s: int) -> None:
        self._data[key] = (time.monotonic() + ttl_s, value)
