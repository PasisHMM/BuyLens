"""Job queue (arq on Redis) and a small per-user rate limiter."""

import time
from typing import Protocol
from uuid import UUID

from arq.connections import ArqRedis
from redis.asyncio import Redis

JOB_NAME = "run_check_job"


class CheckQueue(Protocol):
    async def enqueue(self, run_id: UUID) -> None: ...


class ArqCheckQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    async def enqueue(self, run_id: UUID) -> None:
        # Job id = run id, so a double submit can never start two workers on one run.
        await self._pool.enqueue_job(JOB_NAME, str(run_id), _job_id=f"check:{run_id}")


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        """Count one event; False if the limit for the current window is exceeded."""
        ...


class RedisRateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        bucket = f"buylens:rl:{key}:{int(time.time() // window_s)}"
        count = await self._redis.incr(bucket)
        if count == 1:
            await self._redis.expire(bucket, window_s)
        return int(count) <= limit


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        bucket = f"{key}:{int(time.time() // window_s)}"
        self._counts[bucket] = self._counts.get(bucket, 0) + 1
        return self._counts[bucket] <= limit
