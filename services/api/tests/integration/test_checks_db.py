"""Check-run SQL against real Postgres (CI): worker store (service role) + API repo (RLS)."""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.db import Database
from app.pipeline.cache import MemoryCache
from app.pipeline.models import (
    Candidate,
    Match,
    MemorySnapshot,
    Narrative,
    ProductExtract,
    ProfileSnapshot,
)
from app.pipeline.progress import MemoryEventBus
from app.pipeline.run_check import PipelineDeps, run_check
from app.pipeline.seller_risk import ReviewSummary
from app.pipeline.store import PgCheckStore
from app.repos.checks import PgCheckRepo
from tests.fakes import FakeFetcher, FakeLLM, fixture

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]
PROFILE = ProfileSnapshot(unit="in", measurements_cm={"waist": 66.0, "inseam": 76.2, "hips": 91.4})


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    database = await Database.connect(Settings(database_url=DATABASE_URL or ""))
    yield database
    await database.close()


@pytest.fixture
async def test_seller(db):
    """A throwaway allow-listed seller on a .test domain, removed afterwards."""
    domain = f"brand-{uuid4().hex[:8]}.test"
    async with db.pool.acquire() as conn:
        levis = await conn.fetchval("select id from brands where slug = 'levis'")
        seller_id = await conn.fetchval(
            """insert into sellers (name, domain, official_brand, adapter, trust_rating, return_policy)
               values ('Test official store', $1, $2, 'jsonld', 4.8,
                       '{"verified": true, "window_days": 30, "free": true, "title": "30-day free returns"}')
               returning id""",
            domain,
            levis,
        )
    yield domain
    async with db.pool.acquire() as conn:
        await conn.execute("delete from sellers where id = $1", seller_id)


async def new_user(db: Database) -> UUID:
    user_id = uuid4()
    async with db.pool.acquire() as conn:
        await conn.execute("insert into auth.users (id) values ($1)", user_id)
        await conn.execute("insert into profiles (user_id) values ($1)", user_id)
    return user_id


async def test_full_check_round_trip(db, test_seller):
    repo, store = PgCheckRepo(db), PgCheckStore(db)
    user = await new_user(db)
    url = f"https://www.{test_seller}/p/501"

    assert test_seller in await repo.seller_domains()
    run_id = await repo.create_run(user, input_url=url, profile=PROFILE, memory=await repo.memory_snapshot(user),
                                   pipeline_version="test")  # fmt: skip
    assert await repo.status(user, run_id) == "queued"
    assert await repo.active_runs(user) == 1

    page = fixture("brand_product.html").replace(
        "https://www.brand.test/us/501-original-cropped-jeans/p/A1234", url
    )
    llm = FakeLLM({ReviewSummary: ReviewSummary(themes=["classic"], fit_signal="unknown", red_flags=[])})
    deps = PipelineDeps(store=store, bus=MemoryEventBus(), fetcher=FakeFetcher({url: page}), llm=llm,
                        cache=MemoryCache(), cache_ttl_s=60)  # fmt: skip
    await run_check(deps, run_id)

    result = await repo.get(user, run_id)
    assert result is not None
    assert (result.status, result.verdict, result.selected_size) == ("done", "CONSIDER", "W26 / L30")
    assert result.product is not None and result.product.brand == "Levi's"
    assert result.headline == "Check the hips before you buy."
    assert result.why_not is not None and result.why_not.buy
    assert len(result.options) == 1
    option = result.options[0]
    assert option.seller.domain == test_seller
    assert option.seller_risk.is_official and option.seller_risk.level == "low"
    assert [r.dimension for r in option.fit_check.rows] == ["waist", "inseam", "hips"]

    recent = await repo.recent(user, 5)
    assert recent[0].id == run_id and recent[0].total_cents == 9800 and recent[0].verdict == "CONSIDER"

    # A second worker can't claim the same run.
    assert await store.load_run(run_id) is None


async def test_runs_are_private(db):
    repo = PgCheckRepo(db)
    alice, bob = await new_user(db), await new_user(db)
    run_id = await repo.create_run(alice, input_url="https://levi.com/p", profile=PROFILE, memory=MemorySnapshot(),
                                   pipeline_version="test")  # fmt: skip
    assert await repo.get(bob, run_id) is None
    assert await repo.status(bob, run_id) is None
    assert await repo.cancel_queued(bob, run_id) is False
    assert await repo.recent(bob, 5) == []
    assert await repo.cancel_queued(alice, run_id) is True
    assert await PgCheckStore(db).load_run(run_id) is None  # cancelled before the worker started


async def test_listing_upsert_and_known_candidates(db, test_seller):
    store = PgCheckStore(db)
    seller = next(s for s in await store.sellers() if s.domain == test_seller)
    url = f"https://www.{test_seller}/p/{uuid4().hex[:6]}"
    extract = ProductExtract(url=url, canonical_url=url, seller_domain=test_seller, name="Test Jean",
                             brand="Levi's", mpn=f"MPN-{uuid4().hex[:6]}", price_cents=9800)  # fmt: skip
    candidate = Candidate(extract=extract, seller=seller, match=Match.EXACT)
    brand_id = await store.brand_id("levi's")

    product_id, listing_id = await store.save_listing(candidate, brand_id)
    extract.price_cents = 8800
    product_again, listing_again = await store.save_listing(candidate, brand_id)
    assert (product_again, listing_again) == (product_id, listing_id)

    known = await store.known_candidates(product_id, 3600)
    assert [c.extract.price_cents for c in known] == [8800]
    assert await store.known_candidates(product_id, 0) == []

    # Brand-less, MPN-less products no longer collapse into one row.
    a = await store.save_listing(candidate.model_copy(update={"extract": extract.model_copy(
        update={"brand": None, "mpn": None, "canonical_url": f"{url}-a", "url": f"{url}-a"})}), None)  # fmt: skip
    b = await store.save_listing(candidate.model_copy(update={"extract": extract.model_copy(
        update={"brand": None, "mpn": None, "canonical_url": f"{url}-b", "url": f"{url}-b"})}), None)  # fmt: skip
    assert a[0] != b[0]

    summary = ReviewSummary(themes=["soft"], fit_signal="runs_small", red_flags=[])
    await store.save_review_summary(listing_id, summary, "fake")
    assert await store.review_summary(listing_id) == summary


async def test_complete_run_is_ignored_after_cancel(db):
    repo, store = PgCheckRepo(db), PgCheckStore(db)
    user = await new_user(db)
    run_id = await repo.create_run(user, input_url="https://levi.com/p", profile=PROFILE, memory=MemorySnapshot(),
                                   pipeline_version="test")  # fmt: skip
    assert await store.load_run(run_id) is not None
    await store.finish_run(run_id, "cancelled")
    narrative = Narrative(headline="h", explanation="e", why_not_buy=None, why_not_skip=None, option_summaries=[],
                          written_by="template")  # fmt: skip
    from app.pipeline.models import Decision, Verdict

    await store.complete_run(run_id, uuid4(), None, [], Decision(verdict=Verdict.BUY, reasons=[]), narrative)
    assert await repo.status(user, run_id) == "cancelled"
