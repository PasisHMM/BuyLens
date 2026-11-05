"""Result groups, order and the checks that replaced the verdict tests (docs/redesign-plan.md §2.3)."""

from uuid import uuid4

from app.pipeline.models import (
    Candidate,
    FitCheck,
    FitMemoryEntry,
    FitMode,
    FitOutcome,
    Match,
    MemorySnapshot,
    PriceCheck,
    ProductExtract,
    RankedOption,
    ReturnPolicy,
    ShippingPolicy,
)
from app.pipeline.pricing import evaluate_prices
from app.pipeline.ranking import rank, result_group, selected_size, seller_summary
from app.pipeline.seller_risk import ReviewSummary, evaluate_seller
from tests.fakes import seller

LEVIS = uuid4()
FREE_30 = ReturnPolicy(verified=True, window_days=30, free=True, title="30-day free returns")


def candidate(
    price_cents: int = 9800, *, official: bool = True, returns: ReturnPolicy = FREE_30
) -> Candidate:
    url = f"https://shop.test/{price_cents}"
    extract = ProductExtract(
        url=url,
        canonical_url=url,
        seller_domain="shop.test",
        name="Jeans",
        price_cents=price_cents,
        currency="EUR",
        shipping_cents=0,
    )
    return Candidate(
        extract=extract,
        seller=seller(
            "shop.test",
            name="Shop",
            official_brand_id=LEVIS if official else None,
            trust=4.8,
            returns=returns,
        ),
        match=Match.EXACT,
        is_official=official,
    )


def option(
    outcome: FitOutcome, total: int, *, size: str | None = "M", level: str | None = "low"
) -> RankedOption:
    c = candidate(total)
    risk = evaluate_seller(c, None).model_copy(update={"level": level})
    return RankedOption(
        rank=0,
        candidate=c,
        price=PriceCheck(
            currency="EUR", listing_cents=total, shipping_cents=0, total_cents=total, total_is_estimate=False
        ),
        fit=FitCheck(mode=FitMode.PERSONAL_FIT, outcome=outcome, size_label=size),
        risk=risk,
    )


# ── Groups and order ──


def test_mismatches_are_hidden_and_the_other_outcomes_are_visible() -> None:
    assert result_group(FitOutcome.MATCH) == "matches"
    assert result_group(FitOutcome.UNCERTAIN) == "uncertain"
    assert result_group(FitOutcome.MISMATCH) == "hidden"


def test_a_match_ranks_above_a_cheaper_uncertain_option_and_a_mismatch_comes_last() -> None:
    ranked = rank(
        [
            option(FitOutcome.MISMATCH, 1000),
            option(FitOutcome.UNCERTAIN, 2000),
            option(FitOutcome.MATCH, 9000),
        ]
    )
    assert [o.fit.outcome for o in ranked] == [FitOutcome.MATCH, FitOutcome.UNCERTAIN, FitOutcome.MISMATCH]
    assert [o.rank for o in ranked] == [1, 2, 3]


def test_the_lowest_total_comes_first_within_a_group() -> None:
    ranked = rank([option(FitOutcome.MATCH, 9000), option(FitOutcome.MATCH, 5000)])
    assert [o.price.total_cents for o in ranked] == [5000, 9000]


def test_seller_level_only_breaks_a_tie_on_price() -> None:
    ranked = rank(
        [
            option(FitOutcome.MATCH, 5000, level=None),
            option(FitOutcome.MATCH, 5000, level="high"),
            option(FitOutcome.MATCH, 5000, level="low"),
            option(FitOutcome.MATCH, 5000, level="medium"),
        ]
    )
    assert [o.risk.level for o in ranked] == ["low", "medium", "high", None]


def test_every_option_is_kept_however_many_there_are() -> None:
    assert len(rank([option(FitOutcome.MISMATCH, 1000 + i) for i in range(6)])) == 6


def test_the_selected_size_never_comes_from_a_hidden_option() -> None:
    assert selected_size([option(FitOutcome.MISMATCH, 1000, size="XL")]) is None
    uncertain = option(FitOutcome.UNCERTAIN, 2000, size="S / M")
    assert selected_size([option(FitOutcome.MISMATCH, 1000, size="XL"), uncertain]) == "S / M"


def test_the_selected_size_skips_options_without_one() -> None:
    assert (
        selected_size([option(FitOutcome.UNCERTAIN, 1000, size=None), option(FitOutcome.MATCH, 2000)]) == "M"
    )


# ── Seller summary ──


def test_seller_summary_states_facts() -> None:
    official = evaluate_seller(candidate(), None)
    assert seller_summary(official) == "Official store · 30-day free returns"
    unverified = evaluate_seller(candidate(official=False, returns=ReturnPolicy()), None)
    assert seller_summary(unverified) == "Return policy not verified"
    untitled = evaluate_seller(candidate(official=False, returns=ReturnPolicy(verified=True)), None)
    assert seller_summary(untitled) == "Return policy"


# ── Price ──


def test_price_check_has_totals_and_no_market_figures() -> None:
    check = evaluate_prices([candidate(9800)])[0].model_dump()
    assert check == {
        "currency": "EUR",
        "listing_cents": 9800,
        "shipping_cents": 0,
        "total_cents": 9800,
        "total_is_estimate": False,
    }


def test_unknown_shipping_is_never_free() -> None:
    c = candidate()
    c.extract.shipping_cents = None
    check = evaluate_prices([c])[0]
    assert (check.shipping_cents, check.total_is_estimate) == (None, True)
    c.seller.shipping_policy = ShippingPolicy(verified=True, free_over_cents=7500, flat_cents=600)
    assert evaluate_prices([c])[0].shipping_cents == 0
    c.seller.shipping_policy = ShippingPolicy(verified=False, free_over_cents=7500)
    assert evaluate_prices([c])[0].shipping_cents is None


# ── Seller risk ──


def test_unverified_returns_keep_risk_at_medium() -> None:
    assert evaluate_seller(candidate(returns=ReturnPolicy()), None).level == "medium"
    assert evaluate_seller(candidate(), None).level == "low"


def test_repeated_red_flags_are_high_risk() -> None:
    summary = ReviewSummary(
        themes=["soft denim"], fit_signal="unknown", red_flags=["seams split", "late delivery"]
    )
    assert evaluate_seller(candidate(), summary).level == "high"


def test_free_shipping_starts_exactly_at_the_threshold() -> None:
    c = candidate(7500)
    c.extract.shipping_cents = None
    c.seller.shipping_policy = ShippingPolicy(verified=True, free_over_cents=7500, flat_cents=600)
    assert evaluate_prices([c])[0].shipping_cents == 0
    c.extract.price_cents = 7499
    check = evaluate_prices([c])[0]
    assert check.shipping_cents == 600
    assert check.total_cents == 8099
    assert check.total_is_estimate is False


def test_a_verified_flat_rate_with_no_threshold_is_charged() -> None:
    c = candidate(9800)
    c.extract.shipping_cents = None
    c.seller.shipping_policy = ShippingPolicy(verified=True, flat_cents=600)
    assert evaluate_prices([c])[0].total_cents == 10400


# ── Fit memory: kept for server-side feedback (Phase 7), not applied to fit results today ──


def test_brand_memory_wins_and_cross_brand_memory_counts_half() -> None:
    other = uuid4()
    memory = MemorySnapshot(
        fit=[
            FitMemoryEntry(brand_id=LEVIS, category="jeans", dimension="waist", ease_adjust_cm=2.0),
            FitMemoryEntry(brand_id=None, category="jeans", dimension="waist", ease_adjust_cm=1.0),
        ]
    )
    assert memory.ease_adjust(LEVIS, "jeans", "waist") == 2.0
    assert memory.ease_adjust(other, "jeans", "waist") == 0.5
    assert memory.ease_adjust(None, "jeans", "waist") == 0.5
    assert memory.ease_adjust(LEVIS, "jeans", "hips") == 0.0
    assert memory.ease_adjust(LEVIS, "tops", "waist") == 0.0
