"""Fit, price, seller risk, ranking and verdict rules, checked against the design's example:
Levi's 501 Original Cropped, W26/L30, $98 at the official store, hips not listed → CONSIDER."""

from uuid import uuid4

import pytest

from app.pipeline import narrate, rules
from app.pipeline.fitting import choose_size, evaluate_fit
from app.pipeline.models import (
    Candidate,
    Decision,
    FitMatch,
    FitMemoryEntry,
    Match,
    Measure,
    MemorySnapshot,
    ProductExtract,
    RankedOption,
    ReturnPolicy,
    ShippingPolicy,
    SizeChart,
    SizeRow,
    Verdict,
)
from app.pipeline.pricing import evaluate_prices
from app.pipeline.seller_risk import ReviewSummary, evaluate_seller
from tests.fakes import DESIGN_PROFILE, seller

IN = 2.54
LEVIS = uuid4()
FREE_30 = ReturnPolicy(verified=True, window_days=30, free=True, title="30-day free returns")


def jeans(price_cents=9800, *, stretch=False, chart_basis="garment", waist_garment=27, url="https://levi.test/p/501",
          gtins=("0260",), sizes=("25x30", "26x30", "26x32", "27x30"), hips=None) -> ProductExtract:  # fmt: skip
    rows = []
    for size in (25, 26, 27):
        measures = {"waist": Measure(cm=round((waist_garment + size - 26) * IN, 1), basis=chart_basis)}
        if hips is not None:
            measures["hips"] = Measure(cm=round((hips + size - 26) * IN, 1), basis=chart_basis)
        rows.append(SizeRow(label=str(size), measures=measures))
    return ProductExtract(
        url=url, canonical_url=url, seller_domain="levi.test", name="501® Original Cropped Jeans", brand="Levi's",
        category="jeans", variant_gtins=list(gtins), price_cents=price_cents, sizes=list(sizes),
        size_chart=SizeChart(rows=rows, source="table"), attributes={"stretch": stretch, "fabric": "100% Cotton"},
    )  # fmt: skip


def option(extract: ProductExtract, *, official=True, returns=FREE_30, prices=None, memory=None, summary=None,
           trust=4.8) -> RankedOption:  # fmt: skip
    memory = memory or MemorySnapshot()
    s = seller("levi.test", name="Levi's official store", official_brand_id=LEVIS if official else None,
               trust=trust, returns=returns)  # fmt: skip
    c = Candidate(extract=extract, seller=s, match=Match.EXACT, is_official=official)
    size = choose_size(extract, DESIGN_PROFILE, memory, LEVIS)
    fit = evaluate_fit(extract, size, DESIGN_PROFILE, memory, LEVIS)
    price = (prices or evaluate_prices([c]))[0]
    risk = evaluate_seller(c, summary)
    return RankedOption(
        rank=1,
        candidate=c,
        price=price,
        fit=fit,
        risk=risk,
        score=rules.score(price, fit, risk, memory.decision),
    )


# ── Fit ────────────────────────────────────────────────────────────────────────
def test_size_choice_uses_length_variants():
    size = choose_size(jeans(), DESIGN_PROFILE, MemorySnapshot(), LEVIS)
    assert size is not None
    assert size.display == "W26 / L30"
    assert size.row is not None and size.row.measures["inseam"].cm == round(30 * IN, 1)


def test_design_fit_card():
    fit = option(jeans()).fit
    rows = {r.dimension: r for r in fit.rows}
    assert [r.dimension for r in fit.rows] == ["waist", "inseam", "hips"]
    assert rows["waist"].match is FitMatch.OK and rows["waist"].garment_cm == round(27 * IN, 1)
    assert rows["inseam"].match is FitMatch.OK
    assert rows["hips"].match is FitMatch.MISSING and rows["hips"].garment_cm is None
    assert fit.confidence == "limited"
    assert "Hip measurement unavailable" in fit.alerts
    assert fit.notes == 'Waist allows 1" ease; inseam matches; 100% Cotton; no stretch.'


def test_sizes_up_when_the_usual_size_has_no_ease():
    fit = option(jeans(waist_garment=25.5, hips=37.5)).fit  # size 26 measures 25.5 at the waist
    assert fit.size_label == "W27 / L30"
    assert {r.dimension: r.match for r in fit.rows}["waist"] is FitMatch.OK


def test_only_offered_sizes_are_suggested_and_stretch_helps():
    only_26 = ("26x30",)
    tight = option(jeans(waist_garment=25.5, hips=37.5, sizes=only_26)).fit
    assert tight.size_label == "W26 / L30"
    assert {r.dimension: r.match for r in tight.rows}["waist"] is FitMatch.TIGHT
    stretchy = option(jeans(waist_garment=25.5, hips=37.5, sizes=only_26, stretch=True)).fit
    assert {r.dimension: r.match for r in stretchy.rows}["waist"] is FitMatch.OK


def test_fit_memory_makes_a_brand_stricter():
    memory = MemorySnapshot(
        fit=[FitMemoryEntry(brand_id=LEVIS, category="jeans", dimension="hips", ease_adjust_cm=2 * IN)]
    )
    ok = option(jeans(hips=37)).fit  # 1" of hip room passes by default...
    assert {r.dimension: r.match for r in ok.rows}["hips"] is FitMatch.OK
    stricter = option(jeans(hips=37), memory=memory).fit  # ...but not for someone whose Levi's ran tight
    assert {r.dimension: r.match for r in stricter.rows}["hips"] is FitMatch.TIGHT


def test_non_bottoms_are_flagged():
    extract = jeans().model_copy(update={"category": "tops", "size_chart": None})
    fit = evaluate_fit(extract, None, DESIGN_PROFILE, MemorySnapshot(), None)
    assert fit.confidence == "limited"
    assert any("jeans, pants" in a for a in fit.alerts)


# ── Price ──────────────────────────────────────────────────────────────────────
def _cands(*prices: int) -> list[Candidate]:
    return [Candidate(extract=jeans(p, url=f"https://s{i}.test/p"), seller=seller(f"s{i}.test"), match=Match.EXACT)
            for i, p in enumerate(prices)]  # fmt: skip


def test_market_average_needs_three_comparables():
    assert evaluate_prices(_cands(9800, 10800))[0].market_avg_cents is None
    checks = evaluate_prices(_cands(9800, 10800, 11800))
    assert checks[0].market_avg_cents == 10800
    assert (checks[0].delta_cents, checks[0].delta_pct) == (-1000, -9.3)


def test_market_average_trims_outliers_from_five():
    assert evaluate_prices(_cands(5000, 9800, 10000, 10200, 30000))[0].market_avg_cents == 10000


def test_unknown_shipping_is_never_free():
    c = _cands(9800)[0]
    c.extract.shipping_cents = None
    check = evaluate_prices([c])[0]
    assert (check.shipping_cents, check.total_is_estimate) == (None, True)
    c.seller.shipping_policy = ShippingPolicy(verified=True, free_over_cents=7500, flat_cents=600)
    assert evaluate_prices([c])[0].shipping_cents == 0
    c.seller.shipping_policy = ShippingPolicy(verified=False, free_over_cents=7500)
    assert evaluate_prices([c])[0].shipping_cents is None


# ── Seller risk ────────────────────────────────────────────────────────────────
def test_unverified_returns_keep_risk_at_medium():
    assert option(jeans(), returns=ReturnPolicy()).risk.level == "medium"
    assert option(jeans()).risk.level == "low"


def test_repeated_red_flags_are_high_risk():
    summary = ReviewSummary(
        themes=["soft denim"], fit_signal="unknown", red_flags=["seams split", "late delivery"]
    )
    assert option(jeans(), summary=summary).risk.level == "high"


# ── Verdict ────────────────────────────────────────────────────────────────────
def test_design_case_is_consider():
    prices = evaluate_prices(_cands(9800, 10800, 11800))
    decision = rules.decide(option(jeans(), prices=prices))
    assert decision.verdict is Verdict.CONSIDER
    assert decision.reasons == ["FIT_DATA_MISSING"]
    assert decision.missing_dimensions == ["hips"]


def test_all_checks_pass_is_buy():
    decision = rules.decide(option(jeans(hips=37.5)))
    assert decision == Decision(verdict=Verdict.BUY, reasons=[], missing_dimensions=[])


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"extract": jeans(waist_garment=24)}, "FIT_MISMATCH"),
        ({"extract": jeans(hips=37.5), "summary": ReviewSummary(themes=[], fit_signal="unknown",
                                                               red_flags=["a", "b"])}, "SELLER_HIGH_RISK"),
    ],
)  # fmt: skip
def test_hard_failures_are_skip(kwargs, reason):
    decision = rules.decide(option(**kwargs))
    assert decision.verdict is Verdict.SKIP
    assert reason in decision.reasons


def test_overpriced_is_skip():
    prices = evaluate_prices(_cands(15000, 10000, 10000))  # +28.6% vs market
    decision = rules.decide(option(jeans(15000, hips=37.5), prices=prices))
    assert (decision.verdict, decision.reasons) == (Verdict.SKIP, ["OVERPRICED"])


def test_ranking_prefers_value_over_lowest_price():
    good = option(jeans(9800, hips=37.5))
    cheap_risky = option(jeans(9000, hips=37.5), official=False, returns=ReturnPolicy(), trust=2.5)
    ranked = rules.rank([cheap_risky, good])
    assert ranked[0].candidate is good.candidate
    assert [o.rank for o in ranked] == [1, 2]


# ── Copy ───────────────────────────────────────────────────────────────────────
def test_design_case_template_copy():
    prices = evaluate_prices(_cands(9800, 10800, 11800))
    opt = option(jeans(), prices=prices)
    copy = narrate.template_copy([opt], rules.decide(opt))
    assert copy.headline == "Good price. Check the hips before you buy."
    assert copy.explanation == (
        "The waist and inseam look right, the official store is low risk and the price is below the market "
        "average. But the seller doesn't list a hip measurement, so we won't call it a sure fit without one."
    )
    assert copy.why_not_buy is not None and "hip measurement" in copy.why_not_buy
    assert copy.why_not_skip == "The price is competitive, returns are free and no measurement rules it out."
    assert copy.written_by == "template"


def _copy(**overrides):
    base = {"headline": "Good price. Check the hips first.", "explanation": "Hip size isn't listed.",
            "option_summaries": ["Best overall value."]}  # fmt: skip
    return narrate.LLMCopy(**{**base, **overrides})


@pytest.mark.parametrize(
    ("overrides", "ok"),
    [
        ({}, True),
        ({"explanation": "This is a guaranteed fit."}, False),
        ({"headline": "Good price. Check the size.", "explanation": "Waist isn't listed."}, False),  # no hips
        ({"explanation": "Hips not listed, but it's only $79.00."}, False),  # invented price
        ({"explanation": "Hips not listed; it costs $98.00."}, True),
        ({"headline": "Buy it now, hips unknown."}, False),  # contradicts CONSIDER
        ({"option_summaries": ["One.", "Two."]}, False),
    ],
)
def test_copy_guard(overrides, ok):
    opt = option(jeans())
    assert narrate.check_copy(_copy(**overrides), [opt], rules.decide(opt)) is ok


async def test_llm_copy_used_when_it_passes_and_template_otherwise():
    from tests.fakes import FakeLLM

    opt = option(jeans())
    decision = rules.decide(opt)
    good = await narrate.write_copy(
        FakeLLM({narrate.LLMCopy: _copy()}), opt.candidate.extract, [opt], decision
    )
    assert (good.written_by, good.headline) == ("llm", "Good price. Check the hips first.")
    assert good.why_not_buy  # always deterministic

    llm = FakeLLM({narrate.LLMCopy: _copy(explanation="Perfect fit guaranteed.")})
    bad = await narrate.write_copy(llm, opt.candidate.extract, [opt], decision)
    assert bad.written_by == "template"
    assert len(llm.calls) == 2  # one retry

    # The prompt carries fit outcomes, never the user's raw measurements.
    prompt = llm.calls[0][2]
    assert '"room_in"' in prompt and "66.0" not in prompt and "91.4" not in prompt
