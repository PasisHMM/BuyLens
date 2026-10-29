"""Measurement catalog and category fit rules: the single source for what is measured and how strictly.

Rules come from docs/redesign-plan.md §2.1 (approved 2026-10-29). Terms are defined in docs/glossary.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.pipeline.models import Basis, Dimension, FitCategory, QuickSize, SizeSystem


class UnknownMeasurementError(ValueError):
    pass


class UnknownCategoryError(ValueError):
    pass


@dataclass(frozen=True)
class DimensionSpec:
    label: str
    plausible_cm: tuple[float, float]  # adult range; values outside are almost always a unit mix-up


DIMENSIONS: Mapping[Dimension, DimensionSpec] = {
    Dimension.CHEST: DimensionSpec("Chest / bust", (60.0, 180.0)),
    Dimension.WAIST: DimensionSpec("Waist", (45.0, 200.0)),
    Dimension.HIPS: DimensionSpec("Hips", (60.0, 200.0)),
    Dimension.SHOULDERS: DimensionSpec("Shoulders", (30.0, 70.0)),
    Dimension.INSEAM: DimensionSpec("Inseam", (40.0, 120.0)),
    Dimension.SLEEVE: DimensionSpec("Sleeve length", (40.0, 100.0)),
    Dimension.HEIGHT: DimensionSpec("Height", (120.0, 230.0)),
}

# Names stores and users write for the same measurement.
_ALIASES: Mapping[str, Dimension] = {
    "bust": Dimension.CHEST,
    "hip": Dimension.HIPS,
    "shoulder": Dimension.SHOULDERS,
    "sleeve length": Dimension.SLEEVE,
}


@dataclass(frozen=True)
class CategoryRule:
    """Critical measurements outside tolerance mean MISMATCH; secondary ones can only make a fit UNCERTAIN."""

    critical: frozenset[Dimension]
    secondary: frozenset[Dimension]
    body_tol_cm: float  # against a brand's body-measurement chart
    garment_tol_cm: float  # against measurements of the garment itself

    def __post_init__(self) -> None:
        if not self.critical:
            raise ValueError("A category needs at least one critical measurement.")
        if both := self.critical & self.secondary:
            raise ValueError(f"{sorted(both)} listed as both critical and secondary.")
        if self.body_tol_cm <= 0 or self.garment_tol_cm <= 0:
            raise ValueError("A tolerance must be positive.")

    def tolerance_cm(self, basis: Basis) -> float:
        return self.body_tol_cm if basis is Basis.BODY else self.garment_tol_cm


_D = Dimension
CATEGORY_RULES: Mapping[FitCategory, CategoryRule] = {
    FitCategory.BOTTOMS: CategoryRule(frozenset({_D.WAIST, _D.HIPS}), frozenset({_D.INSEAM}), 2.0, 1.0),
    FitCategory.TOPS: CategoryRule(frozenset({_D.CHEST, _D.SHOULDERS}), frozenset({_D.WAIST}), 2.0, 2.0),
    FitCategory.DRESSES: CategoryRule(frozenset({_D.CHEST, _D.WAIST, _D.HIPS}), frozenset(), 2.0, 2.0),
    FitCategory.OUTERWEAR: CategoryRule(
        frozenset({_D.CHEST, _D.SHOULDERS}), frozenset(), 3.0, 3.0
    ),  # room for layers
}

# Product categories from extract.attributes that have agreed rules. Shorts and skirts have none yet.
_PRODUCT_CATEGORIES: Mapping[str, FitCategory] = {
    "jeans": FitCategory.BOTTOMS,
    "pants": FitCategory.BOTTOMS,
    "tops": FitCategory.TOPS,
    "dresses": FitCategory.DRESSES,
    "outerwear": FitCategory.OUTERWEAR,
}


def rule_for(category: FitCategory) -> CategoryRule:
    return CATEGORY_RULES[category]


def fit_category(product_category: str | None) -> FitCategory | None:
    """The rules that apply to an extracted product, or None when no agreed rules exist."""
    return _PRODUCT_CATEGORIES.get(product_category or "")


def parse_dimension(raw: str) -> Dimension:
    name = raw.strip().lower()
    try:
        return _ALIASES.get(name) or Dimension(name)
    except ValueError:
        raise UnknownMeasurementError(f"Unknown measurement: {raw!r}") from None


def parse_category(raw: str) -> FitCategory:
    try:
        return FitCategory(raw.strip().lower())
    except ValueError:
        raise UnknownCategoryError(f"Unknown category: {raw!r}") from None


def is_plausible(dimension: Dimension, cm: float) -> bool:
    low, high = DIMENSIONS[dimension].plausible_cm
    return low <= cm <= high


@dataclass(frozen=True)
class SizeReference:
    """Approximate body range for a standard size. Quick Fit uses it; it never proves a mismatch."""

    system: SizeSystem
    category: FitCategory
    size_label: QuickSize
    dimension: Dimension
    min_cm: float
    max_cm: float
    source: str  # where the range comes from: standard or chart name, edition, URL

    def __post_init__(self) -> None:
        if not self.size_label:
            raise ValueError("A size reference needs a size label.")
        if not self.source.strip():
            raise ValueError("A size reference needs a source.")
        if self.min_cm >= self.max_cm:
            raise ValueError("min_cm must be below max_cm.")
        if not (is_plausible(self.dimension, self.min_cm) and is_plausible(self.dimension, self.max_cm)):
            raise ValueError(f"{self.dimension} range is outside the plausible adult range.")

    def covers(self, cm: float) -> bool:
        return self.min_cm <= cm <= self.max_cm


# Values pending: the source table (e.g. EN 13402-3, or a chosen brand chart) is not approved yet.
# See docs/redesign-plan.md §7. Rows are added here and seeded into public.size_references together.
SIZE_REFERENCES: tuple[SizeReference, ...] = ()
