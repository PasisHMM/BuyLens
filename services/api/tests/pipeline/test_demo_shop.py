# ruff: noqa: RUF001, RUF003  (en dashes are printed size labels)
"""Merchandizable demo chart and its fit outcomes (redesign plan §11). Values are typed out on purpose."""

import pytest

from app.pipeline.demo_shop import (
    DEMO_CHART,
    DEMO_PRODUCTS,
    ChartRange,
    ChartRow,
    DemoProduct,
    personal_fit,
    prototype_fixture,
    quick_fit,
)
from app.pipeline.fit_profile import Measurement
from app.pipeline.measurements import SIZE_REFERENCES
from app.pipeline.models import Basis, Dimension, FitCategory, FitOutcome, QuickSize

D = Dimension
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


def _product(category: FitCategory | None, sold: tuple[str, ...] = LETTERS) -> DemoProduct:
    return DemoProduct(
        "test", "Test", "Test", category, 1000, sold, "https://merchandizable.example/p/test", None
    )


def _body(**cm: float) -> dict[Dimension, Measurement]:
    return {Dimension(d): Measurement(v) for d, v in cm.items()}


def test_all_nine_sizes_and_their_exact_ranges_are_present() -> None:
    actual = [
        (
            r.label,
            r.eu,
            r.uk,
            (r.ranges[D.CHEST].min_cm, r.ranges[D.CHEST].max_cm),
            (r.ranges[D.WAIST].min_cm, r.ranges[D.WAIST].max_cm),
            (r.ranges[D.HIPS].min_cm, r.ranges[D.HIPS].max_cm),
        )
        for r in DEMO_CHART.rows
    ]
    assert actual == EXPECTED


def test_the_chart_is_a_labelled_body_chart_with_only_the_normal_mode() -> None:
    assert DEMO_CHART.title == "Merchandizable — Demo Size Chart"
    assert "not independently verified" in DEMO_CHART.disclaimer
    assert DEMO_CHART.basis is Basis.BODY
    assert DEMO_CHART.sizing_mode == "NORMAL"
    assert DEMO_CHART.unavailable_modes == ("UMSTANDSMODE", "KLEINE GRÖSSEN")


def test_the_chart_invents_no_other_measurements() -> None:
    for row in DEMO_CHART.rows:
        assert set(row.ranges) == {D.CHEST, D.WAIST, D.HIPS}


def test_the_global_catalog_is_untouched() -> None:
    assert SIZE_REFERENCES == ()
    assert [s.value for s in QuickSize] == list(LETTERS)


@pytest.mark.parametrize(("cm", "expected"), [(81.9, False), (82.0, True), (90.0, True), (90.1, False)])
def test_chart_ranges_include_both_ends(cm: float, expected: bool) -> None:
    small = next(r for r in DEMO_CHART.rows if r.label == "S")
    assert small.ranges[D.CHEST].covers(cm) is expected


def test_a_shared_boundary_belongs_to_both_sizes() -> None:
    labels = [r.label for r in DEMO_CHART.rows if r.ranges[D.CHEST].covers(90.0)]
    assert labels == ["S", "M"]


# ── Quick Fit ──


def test_quick_fit_matches_approximately_when_chart_and_product_have_the_size() -> None:
    fit = quick_fit(_product(FitCategory.TOPS), {FitCategory.TOPS: QuickSize.M})
    assert fit.outcome is FitOutcome.MATCH
    assert fit.size_label == "M"
    assert "Approximate fit based on size M" in fit.reasons[0]
    assert any("not independently verified" in r for r in fit.reasons)


def test_quick_fit_uses_the_size_of_the_products_category_only() -> None:
    fit = quick_fit(_product(FitCategory.BOTTOMS), {FitCategory.TOPS: QuickSize.M})
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert fit.reasons == ("Add your Bottoms size.",)


def test_quick_fit_is_uncertain_when_the_product_is_not_sold_in_that_size() -> None:
    fit = quick_fit(_product(FitCategory.TOPS, ("XXS", "XS")), {FitCategory.TOPS: QuickSize.XL})
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert "isn't listed in size XL" in fit.reasons[0]


def test_quick_fit_does_not_map_waist_length_sizes_onto_letters() -> None:
    fit = quick_fit(_product(FitCategory.BOTTOMS, ("29/32", "30/32")), {FitCategory.BOTTOMS: QuickSize.S})
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert fit.size_label is None


def test_quick_fit_is_uncertain_without_fit_rules_for_the_category() -> None:
    fit = quick_fit(_product(None), {FitCategory.TOPS: QuickSize.M})
    assert fit.outcome is FitOutcome.UNCERTAIN


@pytest.mark.parametrize("product", DEMO_PRODUCTS, ids=lambda p: p.id)
@pytest.mark.parametrize("size", [*QuickSize, None])
def test_quick_fit_never_returns_mismatch(product: DemoProduct, size: QuickSize | None) -> None:
    sizes = {} if size is None or product.category is None else {product.category: size}
    assert quick_fit(product, sizes).outcome is not FitOutcome.MISMATCH


# ── Personal Fit ──


def test_tops_stay_uncertain_because_the_chart_has_no_shoulders() -> None:
    fit = personal_fit(_product(FitCategory.TOPS), _body(chest=88.0, shoulders=42.0, waist=70.0))
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert any("doesn't list shoulders" in r for r in fit.reasons)


def test_bottoms_stay_uncertain_because_the_chart_has_no_inseam() -> None:
    fit = personal_fit(_product(FitCategory.BOTTOMS), _body(waist=70.0, hips=95.0, inseam=80.0))
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert any("doesn't list inseam" in r for r in fit.reasons)
    assert fit.size_label == "S"


def test_a_secondary_measurement_outside_the_range_is_uncertain_never_a_mismatch() -> None:
    fit = personal_fit(_product(FitCategory.TOPS, ("S",)), _body(chest=88.0, shoulders=42.0, waist=100.0))
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert "Waist is outside" in fit.reasons[0]
    assert fit.size_label == "S"


def test_impossible_chart_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="min_cm"):
        ChartRange(90.0, 90.0)
    with pytest.raises(ValueError, match="plausible"):
        ChartRow("S", "36", "8", {D.CHEST: ChartRange(10.0, 20.0)})


def test_a_complete_comparison_can_match_at_the_inclusive_ends() -> None:
    fit = personal_fit(_product(FitCategory.DRESSES), _body(chest=82.0, waist=66.0, hips=97.5))
    assert fit.outcome is FitOutcome.MATCH
    assert fit.size_label == "S"


def test_a_critical_measurement_beyond_tolerance_of_every_sold_size_is_a_mismatch() -> None:
    # XS chest is 78–82: 90 is beyond even the ±2 cm body tolerance.
    fit = personal_fit(_product(FitCategory.DRESSES, ("XS",)), _body(chest=90.0, waist=65.0, hips=88.0))
    assert fit.outcome is FitOutcome.MISMATCH
    assert fit.size_label is None


@pytest.mark.parametrize(("chest", "outcome"), [(84.0, FitOutcome.MATCH), (84.1, FitOutcome.MISMATCH)])
def test_body_tolerance_applies_at_its_exact_limit(chest: float, outcome: FitOutcome) -> None:
    fit = personal_fit(_product(FitCategory.DRESSES, ("XS",)), _body(chest=chest, waist=65.0, hips=88.0))
    assert fit.outcome is outcome


def test_tolerance_reaches_downward_too() -> None:
    fit = personal_fit(_product(FitCategory.DRESSES, ("XS",)), _body(chest=76.0, waist=65.0, hips=88.0))
    assert fit.outcome is FitOutcome.MATCH
    below = personal_fit(_product(FitCategory.DRESSES, ("XS",)), _body(chest=75.9, waist=65.0, hips=88.0))
    assert below.outcome is FitOutcome.MISMATCH


def test_a_missing_critical_measurement_is_uncertain_not_invented() -> None:
    fit = personal_fit(_product(FitCategory.DRESSES), _body(chest=88.0))
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert any("Add your waist" in r for r in fit.reasons)


def test_garment_measurements_are_not_compared_with_a_body_chart() -> None:
    garment = {
        D.CHEST: Measurement(88.0, Basis.GARMENT),
        D.WAIST: Measurement(70.0, Basis.GARMENT),
        D.HIPS: Measurement(95.0, Basis.GARMENT),
    }
    fit = personal_fit(_product(FitCategory.DRESSES), garment)
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert any("body" in r for r in fit.reasons)


def test_no_measurements_at_all_is_uncertain() -> None:
    assert personal_fit(_product(FitCategory.TOPS), {}).outcome is FitOutcome.UNCERTAIN


def test_personal_fit_is_uncertain_without_fit_rules_for_the_category() -> None:
    assert personal_fit(_product(None), _body(chest=88.0)).outcome is FitOutcome.UNCERTAIN


def test_waist_length_products_are_never_a_mismatch_on_a_letter_chart() -> None:
    fit = personal_fit(_product(FitCategory.BOTTOMS, ("29/32",)), _body(waist=200.0, hips=200.0))
    assert fit.outcome is FitOutcome.UNCERTAIN
    assert any("waist/length" in r for r in fit.reasons)


# ── Demo products and the generated prototype fixture ──


def test_only_a_real_page_gets_a_product_url() -> None:
    urls = {p.id: p.product_url for p in DEMO_PRODUCTS}
    assert urls["levis-baggy-jeans"] == "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans"
    assert urls["demo-relaxed-sweater"] is None
    assert urls["demo-wide-leg-trousers"] is None


def test_fixture_holds_every_outcome_the_browser_may_show() -> None:
    fixture = prototype_fixture()
    assert fixture["shop"] == {"id": "merchandizable", "name": "Merchandizable"}
    sweater = next(p for p in fixture["products"] if p["id"] == "demo-relaxed-sweater")
    assert list(sweater["quick_fit"]) == [*LETTERS, "none"]
    assert sweater["quick_fit"]["M"]["outcome"] == "match"
    assert sweater["quick_fit"]["none"]["outcome"] == "uncertain"
    # Saying what the chart lacks holds for everyone; asking for a measurement might not.
    assert sweater["personal_fit"] == {
        "outcome": "uncertain",
        "size_label": None,
        "reasons": ["The demo chart doesn't list shoulders."],
    }
    jeans = next(p for p in fixture["products"] if p["id"] == "levis-baggy-jeans")
    assert jeans["quick_fit"]["M"]["outcome"] == "uncertain"


def test_fixture_chart_keeps_exact_numbers_and_separate_labels() -> None:
    rows = prototype_fixture()["chart"]["rows"]
    assert len(rows) == 9
    assert rows[3] == {
        "label": "M",
        "eu": "40–42",
        "uk": "12–14",
        "chest": {"min_cm": 90.0, "max_cm": 98.0},
        "waist": {"min_cm": 74.0, "max_cm": 82.5},
        "hips": {"min_cm": 97.5, "max_cm": 103.5},
    }
