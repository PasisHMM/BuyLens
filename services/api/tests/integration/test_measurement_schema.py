"""Measurement-model schema (migration 20261029000000) against the Python domain model.

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest -m integration
"""

import os
from collections.abc import AsyncIterator
from enum import StrEnum
from uuid import UUID, uuid4

import asyncpg
import pytest

from app.config import Settings
from app.db import Database
from app.pipeline.fit_profile import Measurement, ProfileUpdate
from app.pipeline.models import Basis, Dimension, FitCategory, FitMode, QuickSize, SizeSystem
from app.repos.profiles import PgProfileRepo
from app.units import Unit

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]

WAIST_AND_INSEAM = ProfileUpdate(
    FitMode.PERSONAL_FIT,
    measurements={Dimension.WAIST: Measurement(76.0), Dimension.INSEAM: Measurement(81.0)},
)


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    database = await Database.connect(Settings(database_url=DATABASE_URL or ""))
    yield database
    await database.close()


async def new_auth_user(db: Database) -> UUID:
    user_id = uuid4()
    async with db.pool.acquire() as conn:
        await conn.execute("insert into auth.users (id) values ($1)", user_id)
    return user_id


@pytest.mark.parametrize(
    ("pg_type", "enum"),
    [
        ("fit_mode", FitMode),
        ("measurement_basis", Basis),
        ("fit_category", FitCategory),
        ("size_system", SizeSystem),
        ("quick_size", QuickSize),
    ],
)
async def test_database_enums_match_the_domain_model(db: Database, pg_type: str, enum: type[StrEnum]) -> None:
    async with db.pool.acquire() as conn:
        labels = await conn.fetchval("select enum_range(null::" + pg_type + ")::text[]")
    assert labels == [member.value for member in enum]


async def test_measurement_dimensions_match_the_catalog(db: Database) -> None:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("select dimension from measurement_dimensions")
    assert {r["dimension"] for r in rows} == {d.value for d in Dimension}


async def test_profiles_saved_by_the_current_app_are_personal_fit_body_measurements(db: Database) -> None:
    user = await new_auth_user(db)
    await PgProfileRepo(db).save(user, unit=Unit.CM, update=WAIST_AND_INSEAM, brand_ids=[])

    async with db.pool.acquire() as conn:
        mode = await conn.fetchval("select fit_mode from profiles where user_id = $1", user)
        bases = await conn.fetch("select distinct basis from fit_measurements where user_id = $1", user)
    assert mode == FitMode.PERSONAL_FIT
    assert [r["basis"] for r in bases] == [Basis.BODY]


async def test_unknown_measurement_is_rejected(db: Database) -> None:
    user = await new_auth_user(db)
    await PgProfileRepo(db).save(user, unit=Unit.CM, update=WAIST_AND_INSEAM, brand_ids=[])
    async with db.user_tx(user) as conn:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await conn.execute(
                "insert into fit_measurements (user_id, dimension, value_cm) values ($1, 'neck', 38)", user
            )


async def test_quick_sizes_are_private_to_their_owner(db: Database) -> None:
    alice, bob = await new_auth_user(db), await new_auth_user(db)
    for user in (alice, bob):
        async with db.user_tx(user) as conn:
            await conn.execute("insert into profiles (user_id, fit_mode) values ($1, 'quick_fit')", user)
            await conn.execute(
                "insert into quick_sizes (user_id, category, size) values ($1, 'tops', 'M')", user
            )

    async with db.user_tx(bob) as conn:
        rows = await conn.fetch("select user_id from quick_sizes")
    assert [r["user_id"] for r in rows] == [bob]

    async with db.user_tx(bob) as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "insert into quick_sizes (user_id, category, size) values ($1, 'dresses', 'S')", alice
            )


async def test_size_references_are_public_read_only_and_need_a_source(db: Database) -> None:
    async with db.public_tx() as conn:
        await conn.fetch("select * from size_references")  # readable without signing in

    # public_tx is read-only; a writable transaction shows the grants themselves forbid writes.
    async with db.pool.acquire() as conn, conn.transaction():
        await conn.execute("set local role anon")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "insert into size_references (system, category, size, dimension, min_cm, max_cm, source)"
                " values ('eu', 'tops', 'M', 'chest', 94, 102, 'x')"
            )

    async with db.pool.acquire() as conn, conn.transaction():
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "insert into size_references (system, category, size, dimension, min_cm, max_cm, source)"
                " values ('eu', 'tops', 'M', 'chest', 94, 102, '  ')"
            )
