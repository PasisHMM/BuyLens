"""Postgres access.

User-owned data is always read and written inside `user_tx()`, which switches the
transaction to Supabase's `authenticated` role and sets the JWT `sub` claim. Row-level
security then applies to the API exactly as it would to a browser client, so a bug in
a query cannot leak another user's measurements.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from fastapi import Request

from app.config import Settings

if TYPE_CHECKING:
    from asyncpg.pool import PoolConnectionProxy

type Conn = PoolConnectionProxy[asyncpg.Record]  # lazily evaluated, so the import can stay type-only


async def _init_connection(conn: asyncpg.Connection) -> None:
    for typename in ("json", "jsonb"):
        await conn.set_type_codec(typename, encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


class Database:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, settings: Settings) -> "Database":
        pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            init=_init_connection,
        )
        return cls(pool)

    async def close(self) -> None:
        await self.pool.close()

    @asynccontextmanager
    async def user_tx(self, user_id: UUID) -> AsyncIterator[Conn]:
        claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
            await conn.execute("set local role authenticated")
            yield conn

    @asynccontextmanager
    async def service_tx(self) -> AsyncIterator[Conn]:
        """Worker access: catalog writes and run results. service_role bypasses RLS, so every
        statement here must scope user data by run id itself."""
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("set local role service_role")
            yield conn

    @asynccontextmanager
    async def public_tx(self) -> AsyncIterator[Conn]:
        """Read-only access to public catalog tables, also under RLS (`anon`)."""
        async with self.pool.acquire() as conn, conn.transaction(readonly=True):
            await conn.execute("set local role anon")
            yield conn


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db
