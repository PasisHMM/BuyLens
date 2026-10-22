"""Check worker (arq).

uv run arq app.worker.WorkerSettings
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.config import get_settings
from app.db import Database
from app.llm import build_llm
from app.log_config import configure_logging
from app.pipeline.cache import RedisCache
from app.pipeline.fetch import HttpFetcher
from app.pipeline.progress import Progress, RedisEventBus
from app.pipeline.run_check import PipelineDeps, run_check
from app.pipeline.store import PgCheckStore
from app.pipeline.urls import domain_matches

log = logging.getLogger(__name__)
TIMEOUT_MESSAGE = "This check took too long. Please try again."


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    db = await Database.connect(settings)
    redis = Redis.from_url(settings.redis_url)
    store = PgCheckStore(db)
    # The fetcher may only reach enabled sellers; refreshed from the DB at the start of each job.
    allowed: set[str] = {s.domain for s in await store.sellers()}

    def host_allowed(host: str) -> bool:
        return any(domain_matches(host, d) for d in allowed)

    ctx.update(
        db=db,
        redis=redis,
        allowed=allowed,
        deps=PipelineDeps(
            store=store,
            bus=RedisEventBus(redis),
            fetcher=HttpFetcher(settings, host_allowed),
            llm=build_llm(settings),
            cache=RedisCache(redis),
            cache_ttl_s=settings.listing_cache_ttl_s,
        ),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["deps"].fetcher.aclose()
    await ctx["redis"].aclose()
    await ctx["db"].close()


async def run_check_job(ctx: dict[str, Any], run_id: str) -> None:
    deps: PipelineDeps = ctx["deps"]
    ctx["allowed"].clear()
    ctx["allowed"].update(s.domain for s in await deps.store.sellers())
    try:
        await run_check(deps, UUID(run_id))
    except asyncio.CancelledError:
        # arq cancels the coroutine on job_timeout: don't leave the run "running" forever.
        await asyncio.shield(_mark_timed_out(deps, UUID(run_id)))
        raise


async def _mark_timed_out(deps: PipelineDeps, run_id: UUID) -> None:
    log.warning("check_timed_out", extra={"run_id": str(run_id)})
    await deps.store.finish_run(run_id, "failed", TIMEOUT_MESSAGE)
    await Progress(deps.bus, run_id).finish("failed", TIMEOUT_MESSAGE)


class WorkerSettings:
    functions = (run_check_job,)
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = get_settings().check_job_timeout_s
    max_tries = 1  # a failed check is reported to the user, not silently retried
    max_jobs = 8
    keep_result = 0
