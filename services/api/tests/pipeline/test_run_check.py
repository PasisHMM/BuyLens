"""The whole pipeline with fake I/O: brand page + a Shopify store carrying the same jeans."""

from urllib.parse import quote_plus
from uuid import uuid4

import pytest

from app.pipeline.cache import MemoryCache
from app.pipeline.models import FitCategory, FitMode, FitOutcome, ProfileSnapshot, QuickSize, ReturnPolicy
from app.pipeline.progress import MemoryEventBus
from app.pipeline.run_check import PipelineDeps, run_check
from app.pipeline.seller_risk import ReviewSummary
from app.pipeline.sourcing import search_query
from tests.fakes import FakeFetcher, FakeLLM, MemoryStore, fixture, seller

BRAND_URL = "https://www.brand.test/us/501-original-cropped-jeans/p/A1234"
SHOP_PRODUCT = "https://shop.test/products/501-cropped"
LEVIS_ID = uuid4()


def shopify_search_url(query: str) -> str:
    return f"https://shop.test/search/suggest.json?q={quote_plus(query)}&resources[type]=product&resources[limit]=5"


def world(*, llm: FakeLLM | None = None, brand_page: str | None = None):
    brand = seller("brand.test", name="Levi's official store", official_brand_id=LEVIS_ID, trust=4.8,
                   returns=ReturnPolicy(verified=True, window_days=30, free=True, title="30-day free returns"))  # fmt: skip
    shop = seller("shop.test", name="Denim Market", adapter="shopify", trust=4.1)
    store = MemoryStore([brand, shop], brands={"levi's": LEVIS_ID})
    query = "Levi's 501 original cropped jeans"
    fetcher = FakeFetcher(
        pages={BRAND_URL: brand_page if brand_page is not None else fixture("brand_product.html")},
        json={
            shopify_search_url(query): {"resources": {"results": {"products": [{"url": "/products/501-cropped?v=1"}]}}},
            f"{SHOP_PRODUCT}.js": {
                "id": 7, "title": "Levi's 501 Original Cropped Jeans", "vendor": "Levi's", "type": "Jeans",
                "options": [{"name": "Size"}],
                "variants": [{"price": 9700, "available": True, "option1": "26x30", "barcode": "0000000000260"}],
            },
        },
    )  # fmt: skip
    llm = llm or FakeLLM(
        {
            ReviewSummary: ReviewSummary(
                themes=["classic straight leg"], fit_signal="true_to_size", red_flags=[]
            ),
        }
    )
    bus = MemoryEventBus()
    deps = PipelineDeps(store=store, bus=bus, fetcher=fetcher, llm=llm, cache=MemoryCache(), cache_ttl_s=60)
    return deps, store, bus, fetcher


async def events(bus: MemoryEventBus, run_id):
    return [e for _, e in await bus.read(run_id, "0", 10)]


def test_search_query_matches_fixture():
    from app.pipeline.models import ProductExtract

    e = ProductExtract(
        url="", canonical_url="", seller_domain="", name="501® Original Cropped Jeans", brand="Levi's"
    )
    assert search_query(e) == "Levi's 501 original cropped jeans"


async def test_full_check_design_case():
    deps, store, bus, _ = world()
    run_id = store.add_run(BRAND_URL)

    await run_check(deps, run_id)

    run = store.runs[run_id]
    assert run["status"] == "done", run.get("error")
    # The fixture publishes garment measurements. A body profile can't be compared with them.
    assert run["selected_size"] is None

    options = run["options"]
    assert [o.rank for o in options] == [1, 2]
    assert [o.fit.outcome for o in options] == [FitOutcome.UNCERTAIN, FitOutcome.UNCERTAIN]
    assert options[0].price.total_cents == 9700 and options[0].price.total_is_estimate  # shipping unknown
    assert options[1].risk.seller_name == "Levi's official store"
    assert options[1].risk.is_official
    assert options[1].summary == "Official store · 30-day free returns"
    assert any("can't be compared" in r for r in options[0].fit.reasons)
    # The Shopify listing has no size chart of its own; the brand chart is reused.
    assert {r.dimension: r.chart_min_cm for r in options[0].fit.rows}["waist"] == 68.6

    evs = await events(bus, run_id)
    assert [(e.type, e.step, e.status) for e in evs] == [
        ("step", "product", "active"), ("step", "product", "done"),
        ("step", "prices", "active"), ("step", "prices", "done"),
        ("step", "fit", "active"), ("step", "fit", "done"),
        ("step", "seller", "active"), ("step", "seller", "done"),
        ("complete", None, None),
    ]  # fmt: skip
    done = {e.step: e.detail for e in evs if e.status == "done"}
    assert done["product"] == "501® Original Cropped Jeans, medium wash"
    assert done["prices"] == "97.00 USD total across 2 sellers"
    assert done["fit"] == "No comparable size data"
    assert [e.index for e in evs if e.status == "active"] == [1, 2, 3, 4]
    assert store.steps == ["product", "prices", "fit", "seller"]

    # Review summaries are cached per listing for the next check.
    assert len(store.summaries) == 1


def _garment_profile(**cm: float) -> ProfileSnapshot:
    return ProfileSnapshot(unit="cm", measurements_cm={}, garment_cm=cm)


async def test_garment_measurements_are_compared_with_a_garment_chart():
    deps, store, bus, _ = world()
    store.profile = _garment_profile(waist=68.6, inseam=76.2)
    run_id = store.add_run(BRAND_URL)
    await run_check(deps, run_id)
    run = store.runs[run_id]
    assert run["status"] == "done", run.get("error")
    assert run["selected_size"] == "W26 / L30"
    # Hips are critical, and the chart doesn't list them, so a trustworthy MATCH isn't possible.
    assert {o.fit.outcome for o in run["options"]} == {FitOutcome.UNCERTAIN}
    done = {e.step: e.detail for e in await events(bus, run_id) if e.status == "done"}
    assert done["fit"] == "Waist, inseam compared"


async def test_a_verified_mismatch_is_kept_in_storage_and_ranked_last():
    deps, store, _, _ = world()
    store.profile = _garment_profile(waist=120.0)
    run_id = store.add_run(BRAND_URL)
    await run_check(deps, run_id)
    run = store.runs[run_id]
    assert run["status"] == "done", run.get("error")
    assert {o.fit.outcome for o in run["options"]} == {FitOutcome.MISMATCH}
    assert len(run["options"]) == 2
    assert run["selected_size"] is None


async def test_a_quick_fit_check_never_uses_saved_numbers():
    deps, store, _, _ = world()
    store.profile = ProfileSnapshot(
        unit="cm",
        measurements_cm={},
        fit_mode=FitMode.QUICK_FIT,
        quick_sizes={FitCategory.BOTTOMS: QuickSize.M},
    )
    run_id = store.add_run(BRAND_URL)
    await run_check(deps, run_id)
    for option in store.runs[run_id]["options"]:
        assert option.fit.approximate is True
        assert all(r.user_cm is None for r in option.fit.rows)


async def test_no_llm_still_gives_a_complete_result():
    deps, store, _, _ = world(
        llm=FakeLLM({ReviewSummary: ReviewSummary(themes=[], fit_signal="unknown", red_flags=[])})
    )
    run_id = store.add_run(BRAND_URL)
    await run_check(deps, run_id)
    assert store.runs[run_id]["status"] == "done"


async def test_cancel_between_steps():
    deps, store, bus, _ = world()
    run_id = store.add_run(BRAND_URL)

    def cancel_at_prices(step):
        if step == "prices":
            bus._cancelled.add(run_id)

    store.on_step = cancel_at_prices
    await run_check(deps, run_id)

    assert store.runs[run_id]["status"] == "cancelled"
    evs = await events(bus, run_id)
    assert evs[-1].type == "cancelled"
    assert "fit" not in store.steps


async def test_unreachable_page_fails_with_store_message():
    deps, store, bus, _ = world()
    run_id = store.add_run("https://www.brand.test/us/does-not-exist")
    await run_check(deps, run_id)
    assert store.runs[run_id]["status"] == "failed"
    assert store.runs[run_id]["error"] == "That product page doesn't exist anymore."
    assert (await events(bus, run_id))[-1].message == "That product page doesn't exist anymore."


async def test_unexpected_error_is_reported_generically(monkeypatch):
    deps, store, bus, _ = world()
    run_id = store.add_run(BRAND_URL)

    async def boom(*args, **kwargs):
        raise RuntimeError("db connection reset: secret details")

    monkeypatch.setattr(store, "save_listing", boom)
    await run_check(deps, run_id)
    assert store.runs[run_id]["status"] == "failed"
    message = (await events(bus, run_id))[-1].message
    assert message == "Something went wrong on our side. Please try again."


async def test_already_claimed_run_is_skipped():
    deps, store, bus, fetcher = world()
    run_id = store.add_run(BRAND_URL, status="cancelled")
    await run_check(deps, run_id)
    assert fetcher.requested == []
    assert await events(bus, run_id) == []


@pytest.mark.parametrize("host", ["https://evil.test/p", "https://brand.test.evil.com/p"])
async def test_unsupported_store_fails(host):
    deps, store, _, _ = world()
    run_id = store.add_run(host)
    await run_check(deps, run_id)
    assert store.runs[run_id]["error"] == "We don't support this store yet."


async def test_quick_fit_check_without_a_matching_chart_size_finishes_uncertain():
    deps, store, _, _ = world()
    store.profile = ProfileSnapshot(
        unit="cm", measurements_cm={}, fit_mode="quick_fit", quick_sizes={"bottoms": "M"}
    )
    run_id = store.add_run(BRAND_URL)

    await run_check(deps, run_id)

    run = store.runs[run_id]
    assert run["status"] == "done", run.get("error")
    assert run["options"][0].fit.outcome is FitOutcome.UNCERTAIN


def test_a_snapshot_stored_before_quick_fit_still_loads_as_personal_fit():
    old = ProfileSnapshot.model_validate({"unit": "in", "measurements_cm": {"waist": 66.0}})
    assert old.fit_mode == "personal_fit"
    assert old.quick_sizes == {}
