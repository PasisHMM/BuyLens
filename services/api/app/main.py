from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.auth import JwtVerifier
from app.config import Settings, get_settings
from app.db import Database
from app.log_config import configure_logging
from app.pipeline.progress import RedisEventBus
from app.queue import ArqCheckQueue, RedisRateLimiter
from app.routers import brands, checks, health, profile


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db = await Database.connect(settings)
        redis = Redis.from_url(settings.redis_url)
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.bus = RedisEventBus(redis)
        app.state.queue = ArqCheckQueue(arq_pool)
        app.state.rate_limiter = RedisRateLimiter(redis)
        try:
            yield
        finally:
            await arq_pool.aclose()
            await redis.aclose()
            await app.state.db.close()

    app = FastAPI(
        title="Buy Lens API",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "prod" else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.verifier = JwtVerifier(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "PUT", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(brands.router)
    app.include_router(checks.router)
    return app
