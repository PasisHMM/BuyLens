"""Saving Quick Fit and Personal Fit sections against a real Postgres (redesign plan §9.3, U4).

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest -m integration
"""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import asyncpg
import pytest

from app.config import Settings
from app.db import Database
from app.pipeline.fit_profile import Measurement, ProfileUpdate
from app.pipeline.models import Basis, Dimension, FitCategory, FitMode, QuickSize, SizeSystem
from app.repos.profiles import PgProfileRepo, UnknownBrandError
from app.units import Unit

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]

QUICK = ProfileUpdate(
    FitMode.QUICK_FIT,
    SizeSystem.EU,
    quick_sizes={FitCategory.TOPS: QuickSize.S, FitCategory.BOTTOMS: QuickSize.M},
)
PERSONAL = ProfileUpdate(
    FitMode.PERSONAL_FIT,
    measurements={
        Dimension.WAIST: Measurement(66.0),
        Dimension.HIPS: Measurement(98.0, Basis.GARMENT, "My blue jeans"),
    },
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


async def _saved(repo: PgProfileRepo, user: UUID, update: ProfileUpdate, *, unit: Unit = Unit.CM) -> None:
    await repo.save(user, unit=unit, update=update, brand_ids=None)


async def test_tops_and_bottoms_are_stored_as_two_rows(db: Database) -> None:
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    await _saved(repo, user, QUICK)

    async with db.user_tx(user) as conn:
        assert await conn.fetchval("select count(*) from quick_sizes") == 2
    stored = await repo.get(user)
    assert stored is not None
    assert stored.fit.mode is FitMode.QUICK_FIT
    assert stored.fit.size_system is SizeSystem.EU
    assert stored.fit.quick_sizes == QUICK.quick_sizes


async def test_saving_quick_sizes_keeps_measurements_and_the_reverse(db: Database) -> None:
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    await _saved(repo, user, PERSONAL)
    await _saved(repo, user, QUICK)
    stored = await repo.get(user)
    assert stored is not None
    assert stored.fit.measurements == PERSONAL.measurements

    await _saved(repo, user, ProfileUpdate(FitMode.PERSONAL_FIT))
    stored = await repo.get(user)
    assert stored is not None
    assert stored.fit.mode is FitMode.PERSONAL_FIT
    assert stored.fit.quick_sizes == QUICK.quick_sizes
    assert stored.fit.size_system is SizeSystem.EU


async def test_basis_and_note_round_trip(db: Database) -> None:
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    await _saved(repo, user, PERSONAL)
    stored = await repo.get(user)
    assert stored is not None
    assert stored.fit.measurements[Dimension.HIPS] == Measurement(98.0, Basis.GARMENT, "My blue jeans")


async def test_saving_the_same_request_twice_gives_the_same_rows(db: Database) -> None:
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    await _saved(repo, user, QUICK)
    first = await repo.get(user)
    await _saved(repo, user, QUICK)
    second = await repo.get(user)
    assert first is not None and second is not None
    assert first.fit == second.fit


async def test_a_provided_section_replaces_the_stored_one(db: Database) -> None:
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    await _saved(repo, user, QUICK)
    await _saved(repo, user, ProfileUpdate(FitMode.QUICK_FIT, quick_sizes={FitCategory.BOTTOMS: QuickSize.L}))
    stored = await repo.get(user)
    assert stored is not None
    assert stored.fit.quick_sizes == {FitCategory.BOTTOMS: QuickSize.L}


async def test_a_failure_mid_save_leaves_nothing_half_written(db: Database) -> None:
    repo, user = PgProfileRepo(db), await new_auth_user(db)
    await _saved(repo, user, QUICK)
    # Unknown brand fails last, after the mode and sizes were written in the same transaction.
    with pytest.raises(UnknownBrandError):
        await repo.save(user, unit=Unit.CM, update=PERSONAL, brand_ids=[uuid4()])
    stored = await repo.get(user)
    assert stored is not None
    assert stored.fit.mode is FitMode.QUICK_FIT
    assert stored.fit.measurements == {}


async def test_another_user_cannot_read_or_change_quick_sizes(db: Database) -> None:
    repo = PgProfileRepo(db)
    alice, bob = await new_auth_user(db), await new_auth_user(db)
    await _saved(repo, alice, QUICK)
    assert await repo.get(bob) is None
    async with db.user_tx(bob) as conn:
        assert await conn.fetchval("select count(*) from quick_sizes") == 0
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "insert into quick_sizes (user_id, category, size) values ($1, 'tops', 'XL')", alice
            )
