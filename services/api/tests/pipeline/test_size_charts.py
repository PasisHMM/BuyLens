# ruff: noqa: RUF001  (en dashes are printed ranges)
"""Published intervals, and page charts as the fit engine reads them."""

from decimal import Decimal

import pytest

from app.pipeline.models import Basis, Dimension, Measure, ProductExtract, SizeChart, SizeRow
from app.pipeline.size_charts import ChartSize, FitChart, Interval, chart_from_extract

WAIST = Interval(60, 70)


@pytest.mark.parametrize(("cm", "expected"), [(59.9, False), (60, True), (70, True), (70.1, False)])
def test_an_interval_includes_both_ends_and_nothing_more_by_default(cm: float, expected: bool) -> None:
    assert WAIST.covers(cm) is expected


def test_below_and_above_extend_only_their_own_side() -> None:
    assert WAIST.covers(58, below_cm=2)
    assert not WAIST.covers(57.9, below_cm=2)
    assert not WAIST.covers(72, below_cm=2)
    assert WAIST.covers(72, above_cm=2)
    assert not WAIST.covers(72.1, above_cm=2)
    assert not WAIST.covers(58, above_cm=2)


def test_arithmetic_is_exact() -> None:
    assert Interval(66.1, 70).covers(64.1, below_cm=2.0)
    assert Interval(60, 70.1).covers(70.3, above_cm=0.2)


@pytest.mark.parametrize(("cm", "distance"), [(55, "5"), (60, "0"), (65, "0"), (70, "0"), (72.5, "2.5")])
def test_distance_is_zero_inside_and_exact_outside(cm: float, distance: str) -> None:
    assert WAIST.distance_to(cm) == Decimal(distance)


@pytest.mark.parametrize(
    ("other", "gap"),
    [
        (Interval(70, 80), "0"),  # touching
        (Interval(65, 80), "0"),  # overlapping
        (Interval(72.5, 80), "2.5"),
        (Interval(50, 57), "3"),
    ],
)
def test_gap_is_the_empty_space_between_two_intervals(other: Interval, gap: str) -> None:
    assert WAIST.gap_to(other) == Decimal(gap)
    assert other.gap_to(WAIST) == Decimal(gap)


def test_touching_is_not_overlapping() -> None:
    assert not WAIST.overlaps_beyond_touching(Interval(70, 80))
    assert WAIST.overlaps_beyond_touching(Interval(69.9, 80))
    assert not WAIST.overlaps_beyond_touching(Interval(71, 80))


def test_a_single_value_is_a_point() -> None:
    assert Interval(66, 66).is_point
    assert not WAIST.is_point
    assert Interval(66, 66).text == "66 cm"
    assert Interval(97.5, 103.5).text == "97.5–103.5 cm"


def test_an_inverted_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="min_cm"):
        Interval(70, 60)


def test_basis_defaults_to_body() -> None:
    assert WAIST.basis is Basis.BODY


# ── FitChart ──

CHART = FitChart(
    (
        ChartSize("S", {Dimension.WAIST: WAIST}),
        ChartSize("M", {Dimension.WAIST: Interval(70, 80), Dimension.HIPS: Interval(95, 105)}),
    )
)


def test_a_chart_finds_sizes_and_what_it_lists() -> None:
    assert CHART.size("M") is CHART.sizes[1]
    assert CHART.size("XL") is None
    assert CHART.lists(Dimension.HIPS)
    assert not CHART.lists(Dimension.SHOULDERS)


def test_with_no_list_from_the_store_every_size_is_offered() -> None:
    assert CHART.offered(()) == CHART.sizes
    assert CHART.offered(("M",)) == (CHART.sizes[1],)
    assert CHART.offered(("XL",)) == ()


# ── From a product page ──


def page(sizes: list[str], rows: list[SizeRow] | None) -> ProductExtract:
    return ProductExtract(
        url="https://shop.test/p",
        canonical_url="https://shop.test/p",
        seller_domain="shop.test",
        name="Jeans",
        price_cents=100,
        sizes=sizes,
        size_chart=SizeChart(rows=rows, source="table") if rows else None,
    )


def row(label: str, **measures: Measure) -> SizeRow:
    return SizeRow(label=label, measures=measures)


WAIST_26 = Measure(cm=68.0, min_cm=66.0, max_cm=70.0, basis=Basis.BODY)


def test_a_page_without_a_chart_has_none() -> None:
    assert chart_from_extract(page(["M"], None)) == (None, ("M",))


def test_a_measure_with_a_range_becomes_that_interval_and_without_one_a_point() -> None:
    chart, _ = chart_from_extract(
        page([], [row("26", waist=WAIST_26, hips=Measure(cm=90, basis=Basis.GARMENT))])
    )
    assert chart is not None
    ranges = chart.sizes[0].ranges
    assert ranges[Dimension.WAIST] == Interval(66.0, 70.0, Basis.BODY)
    assert ranges[Dimension.HIPS] == Interval(90, 90, Basis.GARMENT)


def test_unknown_measures_are_ignored() -> None:
    chart, _ = chart_from_extract(
        page([], [row("26", waist=WAIST_26, neck=Measure(cm=38, basis=Basis.BODY))])
    )
    assert chart is not None
    assert set(chart.sizes[0].ranges) == {Dimension.WAIST}


def test_length_variants_add_a_garment_inseam_in_centimeters() -> None:
    chart, labels = chart_from_extract(page(["26x30", "26x32"], [row("26", waist=WAIST_26)]))
    assert chart is not None
    assert labels == ("26x30", "26x32")
    assert chart.sizes[0].ranges[Dimension.INSEAM] == Interval(76.2, 76.2, Basis.GARMENT)
    assert chart.sizes[1].ranges[Dimension.INSEAM] == Interval(81.3, 81.3, Basis.GARMENT)
    assert chart.sizes[0].ranges[Dimension.WAIST] == Interval(66.0, 70.0, Basis.BODY)


def test_sizes_without_a_length_stay_as_they_are() -> None:
    chart, labels = chart_from_extract(
        page(["26", "M"], [row("26", waist=WAIST_26), row("M", waist=WAIST_26)])
    )
    assert chart is not None
    assert [s.label for s in chart.sizes] == ["26", "M"]
    assert labels == ("26", "M")


def test_a_published_inseam_is_not_replaced_by_length_variants() -> None:
    published = Measure(cm=80, basis=Basis.BODY)
    chart, _ = chart_from_extract(page(["26x30"], [row("26", waist=WAIST_26, inseam=published)]))
    assert chart is not None
    assert [s.label for s in chart.sizes] == ["26"]


def test_only_sold_labels_are_offered() -> None:
    _, labels = chart_from_extract(page(["26"], [row("26", waist=WAIST_26), row("28", waist=WAIST_26)]))
    assert labels == ("26",)


def test_with_no_list_from_the_store_nothing_is_restricted() -> None:
    _, labels = chart_from_extract(page([], [row("26", waist=WAIST_26)]))
    assert labels == ()


def test_sizes_the_chart_does_not_describe_stay_listed_and_match_nothing() -> None:
    chart, labels = chart_from_extract(page(["XL"], [row("26", waist=WAIST_26)]))
    assert chart is not None
    assert labels == ("XL",)
    assert chart.offered(labels) == ()
