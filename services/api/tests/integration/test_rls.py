"""Runs against a real Postgres with supabase/ci/auth_stub.sql, the migrations and seed.sql applied.

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest -m integration
"""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import asyncpg
import pytest

from app.config import Settings
from app.db import Database
from app.repos.brands import PgBrandRepo
from app.repos.profiles import PgProfileRepo, UnknownBrandError
from app.units import Unit

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]

DESIGN_CM = {"waist": 66.0, "inseam": 76.2, "hips": 91.4}


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    database = await Database.connect(Settings(database_url=DATABASE_URL or ""))
    yield database
    await database.close()


async def new_auth_user(db: Database) -> UUID:
    user_id = uuid4()
    async with db.pool.acquire() as conn:  # superuser: stands in for Supabase Auth creating the user
        await conn.execute("insert into auth.users (id) values ($1)", user_id)
    return user_id


async def test_profile_round_trip(db):
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    levis = (await PgBrandRepo(db).search("Levi", 1))[0]

    await repo.save(user, unit=Unit.IN, measurements_cm=DESIGN_CM, brand_ids=[levis.id])
    stored = await repo.get(user)

    assert stored is not None
    assert stored.unit is Unit.IN
    assert stored.measurements_cm == DESIGN_CM
    assert [b.slug for b in stored.brands] == ["levis"]

    # Clearing hips deletes the row instead of leaving a stale value.
    await repo.save(user, unit=Unit.IN, measurements_cm={"waist": 66.0, "inseam": 76.2}, brand_ids=[])
    stored = await repo.get(user)
    assert stored is not None
    assert stored.measurements_cm == {"waist": 66.0, "inseam": 76.2}
    assert stored.brands == []


async def test_rls_hides_other_users_rows(db):
    alice, bob = await new_auth_user(db), await new_auth_user(db)
    await PgProfileRepo(db).save(alice, unit=Unit.IN, measurements_cm=DESIGN_CM, brand_ids=[])

    # Even a query with no user filter only sees the caller's own rows.
    async with db.user_tx(bob) as conn:
        assert await conn.fetchval("select count(*) from fit_measurements") == 0
        assert await conn.fetchval("select count(*) from profiles") == 0
    async with db.user_tx(alice) as conn:
        assert await conn.fetchval("select count(*) from fit_measurements") == 3


async def test_rls_blocks_writing_as_someone_else(db):
    alice, bob = await new_auth_user(db), await new_auth_user(db)
    async with db.user_tx(bob) as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("insert into profiles (user_id) values ($1)", alice)


async def test_catalog_is_read_only_for_users(db):
    user = await new_auth_user(db)
    async with db.user_tx(user) as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("insert into brands (name, slug) values ('Fake', 'fake')")


async def test_unknown_brand_maps_to_domain_error(db):
    user = await new_auth_user(db)
    with pytest.raises(UnknownBrandError):
        await PgProfileRepo(db).save(user, unit=Unit.IN, measurements_cm=DESIGN_CM, brand_ids=[uuid4()])


async def test_brand_search_uses_seed(db):
    hits = await PgBrandRepo(db).search("lev", 5)
    assert [b.slug for b in hits] == ["levis"]
