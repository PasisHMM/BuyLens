# ruff: noqa: RUF001, RUF003  (en dashes are printed size ranges)
"""MATCH / UNCERTAIN / MISMATCH (docs/redesign-plan.md §2.3, revised 2026-11-05). Charts are written out."""

from collections.abc import Mapping

import pytest

from app.pipeline.fit_analysis import evaluate_offer, personal_fit, quick_fit
from app.pipeline.fit_profile import Measurement
from app.pipeline.models import (
    Basis,
    Dimension,
    DimensionStatus,
    FitCategory,
    FitMode,
    FitOutcome,
    Measure,
    ProductExtract,
    ProfileSnapshot,
    QuickSize,
    SizeChart,
    SizeRow,
)
from app.pipeline.size_charts import ChartSize, FitChart, Interval

D = Dimension
MATCH, UNCERTAIN, MISMATCH = FitOutcome.MATCH, FitOutcome.UNCERTAIN, FitOutcome.MISMATCH
Ranges = Mapping[str, tuple[float, float]]


def chart(rows: Mapping[str, Ranges], basis: Basis = Basis.BODY) -> FitChart:
    return FitChart(
        tuple(
            ChartSize(label, {D(d): Interval(a, b, basis) for d, (a, b) in ranges.items()})
            for label, ranges in rows.items()
        )
    )


BOTTOMS_CHART = chart(
    {
        "S": {"waist": (60, 70), "hips": (85, 95)},
        "M": {"waist": (70, 80), "hips": (95, 105)},
        "L": {"waist": (80, 90), "hips": (105, 115)},
    }
)
TOPS_CHART = chart(
    {
        "S": {"chest": (80, 90), "shoulders": (38, 42), "waist": (60, 70), "sleeve": (58, 62)},
        "M": {"chest": (90, 100), "shoulders": (42, 46), "waist": (70, 80), "sleeve": (62, 66)},
    }
)


def body(**cm: float) -> dict[Dimension, Measurement]:
    return {D(d): Measurement(v) for d, v in cm.items()}


def jeans(measurements: Mapping[Dimension, Measurement], fit_chart: FitChart | None = BOTTOMS_CHART,
          offered: tuple[str, ...] = ()):  # fmt: skip
    return personal_fit("jeans", fit_chart, offered, measurements)


# ── Personal Fit: shared boundaries ──


def test_waist_exactly_on_a_shared_boundary_is_uncertain() -> None:
    fit = jeans(body(waist=70.0, hips=95.0))
    assert fit.outcome is UNCERTAIN
    assert "both" in fit.reasons[0]
    assert "Waist 70 cm" in fit.reasons[0]
    assert fit.size_label == "S / M"


def test_waist_just_below_the_boundary_matches_the_smaller_size() -> None:
    fit = jeans(body(waist=69.9, hips=90.0))
    assert (fit.outcome, fit.size_label) == (MATCH, "S")


def test_waist_just_above_the_boundary_matches_the_larger_size() -> None:
    fit = jeans(body(waist=70.1, hips=100.0))
    assert (fit.outcome, fit.size_label) == (MATCH, "M")


def test_a_boundary_is_not_ambiguous_when_another_critical_measurement_decides_the_size() -> None:
    # Waist 70 is on S and M, but hips 90 fit only S, so M isn't a real candidate.
    fit = jeans(body(waist=70.0, hips=90.0))
    assert (fit.outcome, fit.size_label) == (MATCH, "S")


def test_touching_ranges_away_from_the_measurement_cause_no_uncertainty() -> None:
    assert jeans(body(waist=65.0, hips=90.0)).outcome is MATCH


def test_the_inclusive_end_of_an_unshared_range_is_inside() -> None:
    assert jeans(body(waist=60.0, hips=85.0)).outcome is MATCH
    assert jeans(body(waist=90.0, hips=115.0)).outcome is MATCH


OVERLAPPING = chart({"S": {"waist": (60, 72), "hips": (85, 97)}, "M": {"waist": (70, 80), "hips": (95, 105)}})


def test_overlapping_ranges_that_do_not_contain_the_measurement_do_not_matter() -> None:
    fit = jeans(body(waist=65.0, hips=90.0), OVERLAPPING)
    assert (fit.outcome, fit.size_label) == (MATCH, "S")


def test_a_measurement_inside_an_overlap_is_uncertain() -> None:
    assert jeans(body(waist=71.0, hips=96.0), OVERLAPPING).outcome is UNCERTAIN


def test_a_shared_boundary_with_an_unsold_size_is_still_uncertain() -> None:
    fit = jeans(body(waist=70.0, hips=95.0), offered=("S",))
    assert (fit.outcome, fit.size_label) == (UNCERTAIN, "S")


# ── Personal Fit: critical mismatches ──


def test_critical_waist_mismatch_names_the_dimension_and_the_comparison() -> None:
    fit = jeans(body(waist=100.0, hips=110.0))
    assert fit.outcome is MISMATCH
    assert fit.size_label is None
    assert "Waist 100 cm" in fit.reasons[0]
    assert "80–90 cm" in fit.reasons[0]
    assert "size L" in fit.reasons[0]


def test_critical_hip_mismatch() -> None:
    fit = jeans(body(waist=85.0, hips=125.0))
    assert fit.outcome is MISMATCH
    assert "Hips 125 cm" in fit.reasons[0]


def test_critical_shoulder_mismatch_on_tops() -> None:
    fit = personal_fit("sweaters", TOPS_CHART, (), body(chest=95.0, shoulders=60.0, waist=75.0, sleeve=64.0))
    assert fit.outcome is MISMATCH
    assert "Shoulders 60 cm" in fit.reasons[0]


def test_critical_mismatch_outranks_secondary_uncertainty() -> None:
    fit = jeans(body(waist=100.0, hips=110.0, inseam=20.0), with_inseam_chart())
    assert fit.outcome is MISMATCH


def test_critical_mismatch_outranks_a_missing_critical_measurement() -> None:
    assert jeans(body(waist=100.0)).outcome is MISMATCH


def test_no_size_fits_when_each_size_fails_a_different_measurement() -> None:
    # Waist fits only S; hips fit only L.
    assert jeans(body(waist=65.0, hips=110.0)).outcome is MISMATCH


def test_only_sold_sizes_count_towards_a_mismatch() -> None:
    fit = jeans(body(waist=85.0, hips=110.0), offered=("S",))
    assert fit.outcome is MISMATCH
    assert "size S" in fit.reasons[0]


@pytest.mark.parametrize(("waist", "outcome"), [(92.0, UNCERTAIN), (92.1, MISMATCH)])
def test_the_approved_tolerance_separates_close_from_mismatch(waist: float, outcome: FitOutcome) -> None:
    fit = jeans(body(waist=waist, hips=110.0))
    assert fit.outcome is outcome


@pytest.mark.parametrize(("waist", "outcome"), [(58.0, UNCERTAIN), (57.9, MISMATCH)])
def test_tolerance_applies_below_the_range_too(waist: float, outcome: FitOutcome) -> None:
    assert jeans(body(waist=waist, hips=90.0)).outcome is outcome


def test_outside_the_range_but_within_tolerance_is_never_a_match() -> None:
    fit = jeans(body(waist=91.0, hips=110.0))
    assert fit.outcome is UNCERTAIN
    assert "tolerance" in fit.reasons[0]
    assert fit.size_label == "L"


def test_boundaries_do_not_suffer_floating_point_errors() -> None:
    # 66.1 - 2.0 is 64.1 only without binary rounding.
    tight = chart({"S": {"waist": (66.1, 70.0), "hips": (85.0, 95.0)}})
    assert jeans(body(waist=64.1, hips=90.0), tight).outcome is UNCERTAIN
    assert jeans(body(waist=64.0, hips=90.0), tight).outcome is MISMATCH


# ── Personal Fit: secondary measurements ──


def with_inseam_chart() -> FitChart:
    return chart(
        {
            "S": {"waist": (60, 70), "hips": (85, 95), "inseam": (76, 80)},
            "M": {"waist": (70, 80), "hips": (95, 105), "inseam": (78, 82)},
            "L": {"waist": (80, 90), "hips": (105, 115), "inseam": (80, 84)},
        }
    )


def test_a_secondary_inseam_mismatch_is_uncertain_never_a_mismatch() -> None:
    fit = jeans(body(waist=65.0, hips=90.0, inseam=90.0), with_inseam_chart())
    assert (fit.outcome, fit.size_label) == (UNCERTAIN, "S")
    assert "Inseam 90 cm" in fit.reasons[0]


def test_a_secondary_sleeve_mismatch_on_tops_is_uncertain() -> None:
    fit = personal_fit("tops", TOPS_CHART, (), body(chest=85.0, shoulders=40.0, waist=65.0, sleeve=75.0))
    assert fit.outcome is UNCERTAIN
    assert "Sleeve 75 cm" in fit.reasons[0]


def test_a_matching_secondary_measurement_keeps_the_match() -> None:
    fit = jeans(body(waist=65.0, hips=90.0, inseam=78.0), with_inseam_chart())
    assert fit.outcome is MATCH


def test_a_secondary_measurement_within_tolerance_is_no_concern() -> None:
    assert jeans(body(waist=65.0, hips=90.0, inseam=81.0), with_inseam_chart()).outcome is MATCH


def test_a_missing_secondary_measurement_does_not_block_a_match() -> None:
    fit = jeans(body(waist=65.0, hips=90.0))
    assert fit.outcome is MATCH
    assert any("Not checked: inseam" in r for r in fit.reasons)


# ── Personal Fit: missing evidence ──


def test_a_missing_critical_measurement_is_uncertain() -> None:
    fit = jeans(body(waist=65.0))
    assert fit.outcome is UNCERTAIN
    assert "Add your hips measurement." in fit.reasons
    assert fit.size_label == "S"


def test_a_critical_measurement_the_chart_lacks_is_uncertain() -> None:
    no_shoulders = chart({"S": {"chest": (80, 90)}})
    fit = personal_fit("tops", no_shoulders, (), body(chest=85.0, shoulders=40.0))
    assert fit.outcome is UNCERTAIN
    assert "The size chart doesn't list shoulders." in fit.reasons


def test_no_measurements_at_all_is_uncertain() -> None:
    assert jeans({}).outcome is UNCERTAIN


def test_no_chart_is_uncertain_and_nothing_is_invented() -> None:
    fit = jeans(body(waist=65.0, hips=90.0), None)
    assert fit.outcome is UNCERTAIN
    assert fit.rows == []


def test_sizes_the_chart_does_not_describe_are_uncertain() -> None:
    fit = jeans(body(waist=200.0, hips=200.0), offered=("29/32", "30/32"))
    assert fit.outcome is UNCERTAIN


def test_one_listed_size_without_data_blocks_a_proven_mismatch() -> None:
    partial = chart({"S": {"waist": (60, 70), "hips": (85, 95)}, "M": {"inseam": (78, 82)}})
    assert jeans(body(waist=100.0, hips=120.0), partial).outcome is UNCERTAIN


# ── Personal Fit: body and garment ──


def test_body_measurements_are_not_compared_with_a_garment_chart() -> None:
    garment = chart({"S": {"waist": (60, 70), "hips": (85, 95)}}, Basis.GARMENT)
    fit = jeans(body(waist=120.0, hips=150.0), garment)
    assert fit.outcome is UNCERTAIN  # even a large difference proves nothing across bases
    assert any("can't be compared" in r for r in fit.reasons)


def test_garment_measurements_are_not_compared_with_a_body_chart() -> None:
    measured = {D.WAIST: Measurement(65.0, Basis.GARMENT), D.HIPS: Measurement(90.0, Basis.GARMENT)}
    assert jeans(measured).outcome is UNCERTAIN


def test_garment_measurements_match_a_garment_chart_with_the_garment_tolerance() -> None:
    garment = chart({"S": {"waist": (60, 70), "hips": (85, 95)}}, Basis.GARMENT)
    measured = {D.WAIST: Measurement(65.0, Basis.GARMENT), D.HIPS: Measurement(90.0, Basis.GARMENT)}
    assert jeans(measured, garment).outcome is MATCH
    over = {D.WAIST: Measurement(71.0, Basis.GARMENT), D.HIPS: Measurement(90.0, Basis.GARMENT)}
    assert jeans(over, garment).outcome is UNCERTAIN  # within the ±1 cm garment tolerance
    too_far = {D.WAIST: Measurement(71.1, Basis.GARMENT), D.HIPS: Measurement(90.0, Basis.GARMENT)}
    assert jeans(too_far, garment).outcome is MISMATCH


def test_stretch_fabric_only_softens_a_garment_mismatch_on_the_tight_side() -> None:
    garment = chart({"S": {"waist": (60, 70), "hips": (85, 95)}}, Basis.GARMENT)
    tight = {D.WAIST: Measurement(73.0, Basis.GARMENT), D.HIPS: Measurement(90.0, Basis.GARMENT)}
    assert personal_fit("jeans", garment, (), tight).outcome is MISMATCH
    assert personal_fit("jeans", garment, (), tight, stretch=True).outcome is UNCERTAIN
    loose = {D.WAIST: Measurement(57.0, Basis.GARMENT), D.HIPS: Measurement(90.0, Basis.GARMENT)}
    assert personal_fit("jeans", garment, (), loose, stretch=True).outcome is MISMATCH


def test_stretch_does_not_change_a_body_chart() -> None:
    fit = personal_fit("jeans", BOTTOMS_CHART, (), body(waist=93.0, hips=110.0), stretch=True)
    assert fit.outcome is MISMATCH


def test_rows_show_the_comparison_for_each_measurement() -> None:
    fit = jeans(body(waist=65.0, hips=90.0))
    rows = {r.dimension: r for r in fit.rows}
    assert (rows["waist"].user_cm, rows["waist"].chart_min_cm, rows["waist"].chart_max_cm) == (65.0, 60, 70)
    assert rows["waist"].status is DimensionStatus.INSIDE
    assert rows["waist"].role == "critical"
    assert rows["inseam"].status is DimensionStatus.MISSING
    assert rows["inseam"].role == "secondary"


def test_personal_fit_is_exact_not_approximate() -> None:
    fit = jeans(body(waist=65.0, hips=90.0))
    assert fit.mode is FitMode.PERSONAL_FIT
    assert fit.approximate is False


# ── Single-value charts ──

POINTS = chart({"26": {"waist": (66, 66), "hips": (90, 90)}, "28": {"waist": (71, 71), "hips": (95, 95)}})


def test_a_single_published_value_is_compatible_within_tolerance() -> None:
    fit = jeans(body(waist=67.0, hips=91.0), POINTS)
    assert (fit.outcome, fit.size_label) == (MATCH, "W26")


def test_single_values_choose_the_nearest_size() -> None:
    wider = chart({"26": {"waist": (66, 66), "hips": (90, 90)}, "27": {"waist": (68, 68), "hips": (92, 92)}})
    assert jeans(body(waist=66.5, hips=90.5), wider).size_label == "W26"


def test_a_value_exactly_between_two_single_values_is_uncertain() -> None:
    wider = chart({"26": {"waist": (66, 66), "hips": (90, 90)}, "27": {"waist": (68, 68), "hips": (92, 92)}})
    assert jeans(body(waist=67.0, hips=91.0), wider).outcome is UNCERTAIN


def test_a_value_beyond_tolerance_of_every_single_value_is_a_mismatch() -> None:
    assert jeans(body(waist=80.0, hips=110.0), POINTS).outcome is MISMATCH


# ── Quick Fit ──


def quick(product_type: str | None = "jeans", fit_chart: FitChart | None = BOTTOMS_CHART,
          offered: tuple[str, ...] = (), **sizes: str):  # fmt: skip
    chosen = {FitCategory(c): QuickSize(s) for c, s in sizes.items()}
    return quick_fit(product_type, fit_chart, offered, chosen)


def test_quick_fit_matches_when_the_chart_lists_every_priority_measurement() -> None:
    fit = quick(bottoms="M")
    assert (fit.outcome, fit.size_label) == (MATCH, "M")
    assert fit.approximate is True
    assert fit.mode is FitMode.QUICK_FIT
    assert "Approximate" in fit.reasons[0]


def test_quick_fit_ignores_touching_ranges_because_it_has_no_exact_measurement() -> None:
    assert quick(bottoms="S").outcome is MATCH


def test_quick_fit_uses_the_size_of_the_products_own_category() -> None:
    fit = quick(tops="M")
    assert fit.outcome is UNCERTAIN
    assert fit.reasons == ["Add your Bottoms size."]


def test_quick_fit_keeps_tops_and_bottoms_separate() -> None:
    bottoms = quick(bottoms="L", tops="S")
    tops = quick("tops", TOPS_CHART, tops="S", bottoms="L")
    assert bottoms.size_label == "L"
    assert tops.size_label == "S"


def test_quick_fit_invents_no_numeric_measurements() -> None:
    fit = quick(bottoms="M")
    assert [r.user_cm for r in fit.rows] == [None, None]
    assert {r.dimension: (r.chart_min_cm, r.chart_max_cm) for r in fit.rows} == {
        "waist": (70, 80),
        "hips": (95, 105),
    }


def test_quick_fit_compares_only_priority_measurements() -> None:
    # Tops: shoulders are the priority measurement; chest is left to Personal Fit.
    fit = quick("tops", TOPS_CHART, tops="S")
    assert fit.outcome is MATCH
    assert [r.dimension for r in fit.rows] == ["shoulders"]


def test_quick_fit_is_uncertain_when_the_chart_lacks_a_priority_measurement() -> None:
    no_shoulders = chart({"S": {"chest": (80, 90)}})
    fit = quick("tops", no_shoulders, tops="S")
    assert fit.outcome is UNCERTAIN
    assert "The size chart doesn't list shoulders." in fit.reasons


def test_quick_fit_is_uncertain_when_the_selected_size_overlaps_its_neighbour() -> None:
    fit = quick(fit_chart=OVERLAPPING, bottoms="S")
    assert fit.outcome is UNCERTAIN
    assert "overlaps" in fit.reasons[0]


def test_quick_fit_is_uncertain_without_a_chart_row_for_the_size() -> None:
    assert quick(bottoms="XL").outcome is UNCERTAIN


def test_quick_fit_is_uncertain_without_a_chart() -> None:
    assert quick(fit_chart=None, bottoms="M").outcome is UNCERTAIN


def test_quick_fit_does_not_map_waist_length_sizes_onto_letters() -> None:
    fit = quick(offered=("29/32",), bottoms="M")
    assert (fit.outcome, fit.size_label) == (UNCERTAIN, None)


def test_quick_fit_is_uncertain_when_the_size_is_not_sold_but_the_ranges_are_close() -> None:
    # M is not sold, and M's waist range touches S's, so a person in M might still fit S.
    fit = quick(offered=("S",), bottoms="M")
    assert fit.outcome is UNCERTAIN
    assert "isn't listed" in fit.reasons[0]


def test_quick_fit_mismatch_needs_a_gap_no_sold_size_can_bridge() -> None:
    # L: waist 80–90. Only S is sold: waist 60–70. Any waist in L is more than the 2 cm tolerance from S.
    fit = quick(offered=("S",), bottoms="L")
    assert fit.outcome is MISMATCH
    assert fit.approximate is True
    assert "Waist" in fit.reasons[0]
    assert "80–90 cm" in fit.reasons[0]
    assert "60–70 cm" in fit.reasons[0]


def test_quick_fit_gap_exactly_at_tolerance_is_not_proof() -> None:
    near = chart(
        {"S": {"waist": (60, 70), "hips": (85, 95)}, "M": {"waist": (72, 80), "hips": (97, 105)}},
    )
    assert quick(fit_chart=near, offered=("S",), bottoms="M").outcome is UNCERTAIN
    apart = chart(
        {"S": {"waist": (60, 70), "hips": (85, 95)}, "M": {"waist": (72.1, 80), "hips": (95, 105)}},
    )
    assert quick(fit_chart=apart, offered=("S",), bottoms="M").outcome is MISMATCH


def test_quick_fit_mismatch_needs_every_sold_size_apart() -> None:
    # S and L are sold. M touches both, so nothing is proven.
    assert quick(offered=("S", "L"), bottoms="M").outcome is UNCERTAIN


def test_quick_fit_never_proves_a_mismatch_from_a_measurement_outside_the_priority_group() -> None:
    chest_only = chart({"S": {"chest": (80, 90)}, "L": {"chest": (110, 120)}})
    assert quick("tops", chest_only, offered=("S",), tops="L").outcome is UNCERTAIN


def test_quick_fit_needs_data_on_every_sold_size_to_prove_a_mismatch() -> None:
    partial = chart({"S": {"waist": (60, 70)}, "M": {"inseam": (70, 75)}, "L": {"waist": (90, 100)}})
    assert quick(fit_chart=partial, offered=("S", "M"), bottoms="L").outcome is UNCERTAIN


# ── Product types ──


@pytest.mark.parametrize("product_type", ["skirts", "shorts", "hats", None, "swimwear"])
def test_types_without_fit_rules_are_uncertain_with_an_explanation(product_type: str | None) -> None:
    personal = personal_fit(product_type, BOTTOMS_CHART, (), body(waist=65.0, hips=90.0))
    quick_result = quick(product_type, bottoms="M", tops="M")
    for fit in (personal, quick_result):
        assert fit.outcome is UNCERTAIN
        assert "fit rules" in fit.reasons[0]


@pytest.mark.parametrize("product_type", ["dresses", "outerwear"])
def test_types_outside_the_mvp_are_uncertain_with_an_explanation(product_type: str) -> None:
    fit = personal_fit(product_type, BOTTOMS_CHART, (), body(waist=65.0, hips=90.0))
    assert fit.outcome is UNCERTAIN
    assert "Not supported in the MVP" in fit.reasons[0]


# ── From a product page ──


def extract(sizes: list[str] | None = None, *, rows: list[SizeRow] | None = None, **attributes: object):
    return ProductExtract(
        url="https://shop.test/p",
        canonical_url="https://shop.test/p",
        seller_domain="shop.test",
        name="Test jeans",
        category="jeans",
        price_cents=1000,
        currency="EUR",
        sizes=sizes or [],
        attributes=dict(attributes),
        size_chart=SizeChart(
            rows=rows
            or [
                SizeRow(
                    label="26",
                    measures={
                        "waist": Measure(cm=68.0, min_cm=66.0, max_cm=70.0, basis=Basis.BODY),
                        "hips": Measure(cm=90.0, min_cm=88.0, max_cm=92.0, basis=Basis.BODY),
                    },
                ),
            ],
            source="table",
        ),
    )


def profile(mode: FitMode = FitMode.PERSONAL_FIT, **cm: float) -> ProfileSnapshot:
    return ProfileSnapshot(unit="cm", measurements_cm=cm, fit_mode=mode)


def test_a_page_chart_keeps_its_published_range() -> None:
    assert evaluate_offer(extract(), profile(waist=67.0, hips=89.0)).outcome is MATCH


def test_a_page_chart_without_a_range_is_a_single_value() -> None:
    rows = [
        SizeRow(
            label="26",
            measures={
                "waist": Measure(cm=68.0, basis=Basis.BODY),
                "hips": Measure(cm=90.0, basis=Basis.BODY),
            },
        )
    ]
    assert evaluate_offer(extract(rows=rows), profile(waist=69.0, hips=91.0)).outcome is MATCH


def test_length_variants_are_one_size_and_never_ambiguous() -> None:
    fit = evaluate_offer(extract(["26x30", "26x32"]), profile(waist=67.0, hips=89.0))
    assert fit.outcome is MATCH
    assert fit.size_label == "W26 / L30"


def test_only_sizes_the_store_sells_are_offered() -> None:
    fit = evaluate_offer(extract(["28"]), profile(waist=67.0, hips=89.0))
    assert fit.outcome is UNCERTAIN


def test_garment_values_in_a_snapshot_reach_a_garment_chart() -> None:
    rows = [
        SizeRow(
            label="26",
            measures={
                "waist": Measure(cm=68.0, min_cm=66.0, max_cm=70.0, basis=Basis.GARMENT),
                "hips": Measure(cm=90.0, min_cm=88.0, max_cm=92.0, basis=Basis.GARMENT),
            },
        )
    ]
    snapshot = ProfileSnapshot(unit="cm", measurements_cm={}, garment_cm={"waist": 67.0, "hips": 89.0})
    assert evaluate_offer(extract(rows=rows), snapshot).outcome is MATCH


def test_stretch_from_a_page_counts_only_with_known_fabric() -> None:
    rows = [
        SizeRow(
            label="26",
            measures={
                "waist": Measure(cm=68.0, min_cm=66.0, max_cm=70.0, basis=Basis.GARMENT),
                "hips": Measure(cm=90.0, min_cm=88.0, max_cm=92.0, basis=Basis.GARMENT),
            },
        )
    ]
    snapshot = ProfileSnapshot(unit="cm", measurements_cm={}, garment_cm={"waist": 73.0, "hips": 89.0})
    assert evaluate_offer(extract(rows=rows, stretch=True), snapshot).outcome is MISMATCH
    with_fabric = extract(rows=rows, stretch=True, fabric="98% cotton, 2% elastane")
    assert evaluate_offer(with_fabric, snapshot).outcome is UNCERTAIN


def test_a_quick_fit_snapshot_uses_quick_sizes() -> None:
    rows = [
        SizeRow(label="M", measures={
            "waist": Measure(cm=68.0, min_cm=66.0, max_cm=70.0, basis=Basis.BODY),
            "hips": Measure(cm=90.0, min_cm=88.0, max_cm=92.0, basis=Basis.BODY),
        })
    ]  # fmt: skip
    snapshot = ProfileSnapshot(
        unit="cm",
        measurements_cm={},
        fit_mode=FitMode.QUICK_FIT,
        quick_sizes={FitCategory.BOTTOMS: QuickSize.M},
    )
    assert evaluate_offer(extract(rows=rows), snapshot).outcome is MATCH


# ── Details of the wording and of partial charts ──


def test_a_near_miss_on_one_measurement_does_not_hide_a_mismatch_on_another() -> None:
    # Waist 91 is within tolerance of L, but hips 125 are far beyond it.
    assert jeans(body(waist=91.0, hips=125.0)).outcome is MISMATCH


def test_the_mismatch_reason_says_closest_only_when_there_was_a_choice() -> None:
    assert "the closest listed size" in jeans(body(waist=100.0, hips=110.0)).reasons[0]
    only_one = jeans(body(waist=100.0, hips=110.0), offered=("L",)).reasons[0]
    assert "closest" not in only_one


def test_ambiguity_is_explained_with_a_measurement_both_sizes_publish() -> None:
    partial = chart({"S": {"waist": (60, 70), "hips": (85, 95)}, "M": {"hips": (95, 105)}})
    fit = jeans(body(waist=65.0, hips=95.0), partial)
    assert fit.outcome is UNCERTAIN
    assert "Hips 95 cm" in fit.reasons[0]


def test_sizes_that_share_no_published_measurement_are_still_ambiguous() -> None:
    apart = chart({"S": {"waist": (60, 70)}, "M": {"hips": (95, 105)}})
    fit = jeans(body(waist=65.0, hips=100.0), apart)
    assert fit.outcome is UNCERTAIN
    assert fit.reasons == ["More than one size fits these measurements."]
