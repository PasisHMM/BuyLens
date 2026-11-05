"""Measurement catalog and category fit rules (docs/redesign-plan.md §2.1)."""

import pytest

from app.pipeline.measurements import (
    CATEGORY_RULES,
    CategoryRule,
    SizeReference,
    UnknownCategoryError,
    UnknownMeasurementError,
    fit_category,
    is_plausible,
    parse_category,
    parse_dimension,
    rule_for,
)
from app.pipeline.models import Basis, Dimension, FitCategory, QuickSize, SizeSystem

D = Dimension


@pytest.mark.parametrize(
    ("category", "critical", "secondary"),
    [
        (FitCategory.BOTTOMS, {D.WAIST, D.HIPS}, {D.INSEAM}),
        (FitCategory.TOPS, {D.CHEST, D.SHOULDERS}, {D.WAIST}),
        (FitCategory.DRESSES, {D.CHEST, D.WAIST, D.HIPS}, set()),
        (FitCategory.OUTERWEAR, {D.CHEST, D.SHOULDERS}, set()),
    ],
)
def test_critical_and_secondary_measurements_per_category(
    category: FitCategory, critical: set[Dimension], secondary: set[Dimension]
) -> None:
    rule = rule_for(category)
    assert rule.critical == critical
    assert rule.secondary == secondary


@pytest.mark.parametrize(
    ("category", "body_cm", "garment_cm"),
    [
        (FitCategory.BOTTOMS, 2.0, 1.0),
        (FitCategory.TOPS, 2.0, 2.0),
        (FitCategory.DRESSES, 2.0, 2.0),
        (FitCategory.OUTERWEAR, 3.0, 3.0),
    ],
)
def test_tolerance_depends_on_category_and_chart_basis(
    category: FitCategory, body_cm: float, garment_cm: float
) -> None:
    rule = rule_for(category)
    assert rule.tolerance_cm(Basis.BODY) == body_cm
    assert rule.tolerance_cm(Basis.GARMENT) == garment_cm


def test_every_category_has_a_rule() -> None:
    assert set(CATEGORY_RULES) == set(FitCategory)


@pytest.mark.parametrize(
    ("product_category", "expected"),
    [
        ("jeans", FitCategory.BOTTOMS),
        ("pants", FitCategory.BOTTOMS),
        ("tops", FitCategory.TOPS),
        ("dresses", FitCategory.DRESSES),
        ("outerwear", FitCategory.OUTERWEAR),
        ("shorts", None),  # no agreed rules yet
        ("skirts", None),
        ("hats", None),
        (None, None),
    ],
)
def test_product_category_maps_to_fit_rules_only_where_rules_exist(
    product_category: str | None, expected: FitCategory | None
) -> None:
    assert fit_category(product_category) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("waist", D.WAIST),
        (" Waist ", D.WAIST),
        ("bust", D.CHEST),  # one body measurement, called bust on women's charts
        ("Chest", D.CHEST),
        ("hip", D.HIPS),
        ("shoulder", D.SHOULDERS),
        ("sleeve length", D.SLEEVE),
        ("inseam", D.INSEAM),
        ("height", D.HEIGHT),
    ],
)
def test_dimension_names_are_parsed_once_at_the_boundary(raw: str, expected: Dimension) -> None:
    assert parse_dimension(raw) is expected


@pytest.mark.parametrize("raw", ["neck", "", "waist2"])
def test_unknown_dimension_is_rejected(raw: str) -> None:
    with pytest.raises(UnknownMeasurementError):
        parse_dimension(raw)


def test_category_names_are_parsed_and_unknown_ones_rejected() -> None:
    assert parse_category("Tops") is FitCategory.TOPS
    with pytest.raises(UnknownCategoryError):
        parse_category("hats")


@pytest.mark.parametrize(
    ("dimension", "cm", "plausible"),
    [
        (D.WAIST, 76.0, True),
        (D.WAIST, 30.0, False),  # inches typed with the cm toggle on
        (D.INSEAM, 81.0, True),
        (D.CHEST, 96.0, True),
        (D.SHOULDERS, 45.0, True),
        (D.SHOULDERS, 96.0, False),
        (D.HEIGHT, 175.0, True),
        (D.HEIGHT, 69.0, False),
    ],
)
def test_plausible_adult_ranges(dimension: Dimension, cm: float, plausible: bool) -> None:
    assert is_plausible(dimension, cm) is plausible


def test_a_rule_cannot_list_a_measurement_as_both_critical_and_secondary() -> None:
    with pytest.raises(ValueError, match="both critical and secondary"):
        CategoryRule(
            critical=frozenset({D.WAIST}), secondary=frozenset({D.WAIST}), body_tol_cm=2, garment_tol_cm=1
        )


def test_a_rule_needs_a_critical_measurement_and_positive_tolerances() -> None:
    with pytest.raises(ValueError, match="critical"):
        CategoryRule(critical=frozenset(), secondary=frozenset(), body_tol_cm=2, garment_tol_cm=1)
    with pytest.raises(ValueError, match="tolerance"):
        CategoryRule(critical=frozenset({D.WAIST}), secondary=frozenset(), body_tol_cm=0, garment_tol_cm=1)


def _reference(**overrides: object) -> SizeReference:
    values: dict[str, object] = {
        "system": SizeSystem.EU,
        "category": FitCategory.TOPS,
        "size_label": "M",
        "dimension": D.CHEST,
        "min_cm": 94.0,
        "max_cm": 102.0,
        "source": "Example chart, https://example.test/sizes",
    }
    return SizeReference(**(values | overrides))  # type: ignore[arg-type]


def test_size_reference_is_a_body_range_with_a_source() -> None:
    ref = _reference()
    assert ref.covers(98.0)
    assert not ref.covers(103.0)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source": "  "}, "source"),
        ({"min_cm": 102.0, "max_cm": 94.0}, "min_cm"),
        ({"size_label": ""}, "size label"),
        ({"min_cm": 10.0}, "plausible"),
    ],
)
def test_size_reference_rejects_unsourced_or_impossible_rows(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _reference(**overrides)


# ── Inclusive limits (docs/redesign-plan.md §2.2): the published ends of a range belong to it. ──


@pytest.mark.parametrize(
    ("cm", "expected"),
    [(44.9, False), (45.0, True), (200.0, True), (200.1, False)],
)
def test_plausible_range_includes_both_ends(cm: float, expected: bool) -> None:
    assert is_plausible(D.WAIST, cm) is expected


def _waist_range(min_cm: float, max_cm: float) -> SizeReference:
    return SizeReference(
        SizeSystem.EU, FitCategory.BOTTOMS, QuickSize.S, D.WAIST, min_cm, max_cm, "test chart"
    )


@pytest.mark.parametrize(
    ("cm", "expected"),
    [(65.9, False), (66.0, True), (70.0, True), (70.1, False)],
)
def test_size_reference_covers_both_published_ends(cm: float, expected: bool) -> None:
    assert _waist_range(66.0, 70.0).covers(cm) is expected


def test_size_reference_rejects_an_empty_range() -> None:
    with pytest.raises(ValueError, match="min_cm"):
        _waist_range(66.0, 66.0)


def test_size_reference_accepts_the_plausible_limits_as_its_ends() -> None:
    assert _waist_range(45.0, 200.0).covers(45.0)


def test_a_tolerance_below_one_centimeter_is_allowed() -> None:
    rule = CategoryRule(frozenset({D.WAIST}), frozenset(), 0.5, 0.5)
    assert rule.tolerance_cm(Basis.BODY) == 0.5


@pytest.mark.parametrize(("body", "garment"), [(0.0, 1.0), (1.0, 0.0)], ids=["body", "garment"])
def test_a_tolerance_of_zero_is_rejected(body: float, garment: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        CategoryRule(frozenset({D.WAIST}), frozenset(), body, garment)
