# ruff: noqa: RUF001  (en dashes are printed size labels)
"""Merchandizable demo chart and its outcomes (redesign plan §11). Values are typed out on purpose."""

import pytest

from app.pipeline.demo_shop import (
    DEMO_CHART,
    DEMO_PRODUCTS,
    DEMO_ROWS,
    PERSONAL_SAMPLES,
    DemoProduct,
    DemoRow,
    demo_personal_fit,
    demo_quick_fit,
    prototype_fixture,
)
from app.pipeline.measurements import SIZE_REFERENCES
from app.pipeline.models import Dimension, FitCategory, FitOutcome, QuickSize
from app.pipeline.taxonomy import ProductType

D = Dimension
MATCH, UNCERTAIN, MISMATCH = FitOutcome.MATCH, FitOutcome.UNCERTAIN, FitOutcome.MISMATCH
EXPECTED = [
    ("XXS", "32", "4", (75, 78), (62, 64), (82, 86)),
    ("XS", "34", "6", (78, 82), (64, 66), (86, 90)),
    ("S", "36–38", "8–10", (82, 90), (66, 74), (90, 97.5)),
    ("M", "40–42", "12–14", (90, 98), (74, 82.5), (97.5, 103.5)),
    ("L", "44–46", "16–18", (98, 107), (82.5, 93), (103.5, 110.5)),
    ("XL", "48–50", "20–22", (107, 119), (93, 105), (110.5, 120.5)),
    ("XXL", "52–54", "24–26", (119, 131), (105, 117.5), (120.5, 131)),
    ("3XL", "56–58", "28–30", (131, 143), (117.5, 131.5), (131, 143)),
    ("4XL", "60–62", "32–34", (143, 155), (131.5, 145.5), (143, 155)),
]
LETTERS = ("XS", "S", "M", "L", "XL")


def product(product_id: str) -> DemoProduct:
    return next(p for p in DEMO_PRODUCTS if p.id == product_id)


SWEATER = product("demo-relaxed-sweater")
TROUSERS = product("demo-wide-leg-trousers")
PETITE = product("demo-petite-trousers")
JEANS = product("levis-baggy-jeans")


def bottoms(size: str) -> dict[FitCategory, QuickSize]:
    return {FitCategory.BOTTOMS: QuickSize(size)}


def test_all_nine_sizes_and_their_exact_ranges_are_present() -> None:
    assert [(r.label, r.eu, r.uk, r.chest, r.waist, r.hips) for r in DEMO_ROWS] == EXPECTED
    small = DEMO_CHART.size("S")
    assert small is not None
    assert (small.ranges[D.WAIST].min_cm, small.ranges[D.WAIST].max_cm) == (66, 74)


def test_the_chart_invents_no_other_measurements() -> None:
    for size in DEMO_CHART.sizes:
        assert set(size.ranges) == {D.CHEST, D.WAIST, D.HIPS}


def test_the_global_catalog_is_untouched() -> None:
    assert SIZE_REFERENCES == ()
    assert [s.value for s in QuickSize] == list(LETTERS)


def test_impossible_chart_rows_are_rejected() -> None:
    fine = (80.0, 90.0)
    with pytest.raises(ValueError, match="min_cm"):
        DemoRow("S", "36", "8", (90.0, 90.0), fine, fine).chart_size()
    for implausible in ((10.0, 80.0), (80.0, 500.0)):  # either end alone is enough
        with pytest.raises(ValueError, match="plausible"):
            DemoRow("S", "36", "8", implausible, fine, fine).chart_size()


# ── Quick Fit ──


@pytest.mark.parametrize("size", LETTERS)
def test_trousers_match_in_every_quick_size(size: str) -> None:
    fit = demo_quick_fit(TROUSERS, bottoms(size))
    assert (fit.outcome, fit.size_label) == (MATCH, size)


@pytest.mark.parametrize("size", LETTERS)
def test_sweaters_stay_uncertain_because_the_chart_has_no_shoulders(size: str) -> None:
    fit = demo_quick_fit(SWEATER, {FitCategory.TOPS: QuickSize(size)})
    assert fit.outcome is UNCERTAIN
    assert "The size chart doesn't list shoulders." in fit.reasons


def test_quick_fit_uses_only_the_products_own_category() -> None:
    fit = demo_quick_fit(TROUSERS, {FitCategory.TOPS: QuickSize.M})
    assert fit.outcome is UNCERTAIN
    assert fit.reasons == ["Add your Bottoms size."]


@pytest.mark.parametrize("size", LETTERS)
def test_waist_length_jeans_are_never_mapped_onto_letters(size: str) -> None:
    fit = demo_quick_fit(JEANS, bottoms(size))
    assert (fit.outcome, fit.size_label) == (UNCERTAIN, None)


@pytest.mark.parametrize(
    ("size", "outcome"),
    [("XS", MATCH), ("S", UNCERTAIN), ("M", MISMATCH), ("L", MISMATCH), ("XL", MISMATCH)],
)
def test_petite_trousers_are_a_proven_quick_fit_mismatch_only_when_far_apart(
    size: str, outcome: FitOutcome
) -> None:
    # Sold in XXS and XS. S touches XS (waist 66), so S can't be ruled out. M starts at 74: 8 cm away.
    assert demo_quick_fit(PETITE, bottoms(size)).outcome is outcome


def test_a_quick_fit_mismatch_explains_the_comparison() -> None:
    reason = demo_quick_fit(PETITE, bottoms("L")).reasons[0]
    assert "Waist for size L is 82.5–93 cm" in reason
    assert "XS" in reason and "64–66 cm" in reason


# ── Personal Fit ──


def cm(sample_id: str) -> dict[Dimension, float]:
    return dict(next(s for s in PERSONAL_SAMPLES if s.id == sample_id).measurements_cm)


def test_measurements_inside_one_size_match_bottoms_without_inventing_an_inseam() -> None:
    fit = demo_personal_fit(TROUSERS, cm("inside-size-s"))
    assert (fit.outcome, fit.size_label) == (MATCH, "S")
    assert any("Not checked: inseam" in r for r in fit.reasons)


def test_tops_cannot_match_without_shoulders() -> None:
    fit = demo_personal_fit(SWEATER, cm("inside-size-s"))
    assert fit.outcome is UNCERTAIN
    assert "The size chart doesn't list shoulders." in fit.reasons


def test_measurements_on_the_shared_line_are_uncertain() -> None:
    fit = demo_personal_fit(TROUSERS, cm("on-the-s-m-line"))
    assert (fit.outcome, fit.size_label) == (UNCERTAIN, "S / M")
    assert "both" in fit.reasons[0]


@pytest.mark.parametrize("item", [TROUSERS, SWEATER], ids=lambda p: p.id)
def test_measurements_above_every_sold_size_are_a_mismatch(item: DemoProduct) -> None:
    assert demo_personal_fit(item, cm("above-the-listed-sizes")).outcome is MISMATCH


def test_a_size_the_product_does_not_sell_cannot_match() -> None:
    assert demo_personal_fit(PETITE, cm("inside-size-s")).outcome is MISMATCH


def test_waist_length_jeans_are_never_a_personal_mismatch_on_a_letter_chart() -> None:
    fit = demo_personal_fit(JEANS, cm("above-the-listed-sizes"))
    assert fit.outcome is UNCERTAIN
    assert "aren't in its size chart" in fit.reasons[0]


# ── The generated prototype fixture ──


def fixture_product(product_id: str) -> dict:
    return next(p for p in prototype_fixture()["products"] if p["id"] == product_id)


def test_only_a_real_page_gets_a_product_url() -> None:
    assert (
        fixture_product("levis-baggy-jeans")["option"]["url"]
        == "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans"
    )
    assert fixture_product("demo-relaxed-sweater")["option"]["url"] == ""


def test_fixture_holds_every_quick_fit_outcome_with_its_group() -> None:
    petite = fixture_product("demo-petite-trousers")
    assert list(petite["quick_fit"]) == [*LETTERS, "none"]
    assert petite["quick_fit"]["XS"]["group"] == "matches"
    assert petite["quick_fit"]["S"]["group"] == "uncertain"
    assert petite["quick_fit"]["M"]["group"] == "hidden"
    assert petite["quick_fit"]["none"]["fit"]["reasons"] == ["Add your Bottoms size."]


def test_every_match_says_the_chart_is_unverified() -> None:
    for item in prototype_fixture()["products"]:
        variants = [*item["quick_fit"].values(), *item["sample_fit"].values()]
        for variant in variants:
            if variant["fit"]["outcome"] == "match":
                assert any("not independently verified" in r for r in variant["fit"]["reasons"])


def test_fixture_holds_python_results_for_each_sample_body() -> None:
    trousers = fixture_product("demo-wide-leg-trousers")["sample_fit"]
    assert {k: v["fit"]["outcome"] for k, v in trousers.items()} == {
        "inside-size-s": "match",
        "on-the-s-m-line": "uncertain",
        "above-the-listed-sizes": "mismatch",
    }


def test_own_measurements_in_the_browser_state_only_what_the_chart_lacks() -> None:
    sweater = fixture_product("demo-relaxed-sweater")["personal_fit"]["fit"]
    assert sweater["outcome"] == "uncertain"
    assert sweater["reasons"] == ["The size chart doesn't list shoulders."]
    assert fixture_product("demo-wide-leg-trousers")["personal_fit"]["fit"]["reasons"] == []


def test_fixture_chart_keeps_exact_numbers_and_separate_labels() -> None:
    fixture = prototype_fixture()
    rows = fixture["chart"]["rows"]
    assert len(rows) == 9
    assert rows[3] == {
        "label": "M",
        "eu": "40–42",
        "uk": "12–14",
        "chest": {"min_cm": 90.0, "max_cm": 98.0},
        "waist": {"min_cm": 74.0, "max_cm": 82.5},
        "hips": {"min_cm": 97.5, "max_cm": 103.5},
    }
    assert fixture["chart"]["title"] == "Merchandizable — Demo Size Chart"
    assert "not independently verified" in fixture["chart"]["disclaimer"]
    assert fixture["chart"]["basis"] == "body"
    assert fixture["chart"]["sizing_mode"] == "NORMAL"
    assert fixture["chart"]["unavailable_modes"] == ["UMSTANDSMODE", "KLEINE GRÖSSEN"]


def test_fixture_uses_controlled_product_types() -> None:
    for item in prototype_fixture()["products"]:
        ProductType(item["product_type"])


def test_a_fixture_option_has_the_response_shape_without_its_fit() -> None:
    option = fixture_product("levis-baggy-jeans")["option"]
    assert option["rank"] == 1
    assert option["seller"]["name"] == "Merchandizable"
    assert option["price_check"]["currency"] == "EUR"
    assert option["total_cents"] == 5500
    assert option["seller_risk"]["level"] is None
    assert "fit_check" not in option
