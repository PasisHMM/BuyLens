"""Size charts as the fit engine reads them: published intervals per size, for any shop.

Ranges are inclusive. Comparisons use exact decimals, so 66.1 - 2.0 is exactly 64.1.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.pipeline.extract.attributes import parse_size_label
from app.pipeline.models import Basis, Dimension, Measure, ProductExtract, SizeRow

CM_PER_IN = Decimal("2.54")


def _exact(value: float) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class Interval:
    min_cm: float
    max_cm: float
    basis: Basis = Basis.BODY

    def __post_init__(self) -> None:
        if self.min_cm > self.max_cm:
            raise ValueError("min_cm must not be above max_cm.")

    @property
    def is_point(self) -> bool:
        """A single published value, with no range around it."""
        return self.min_cm == self.max_cm

    def covers(self, cm: float, below_cm: float | Decimal = 0, above_cm: float | Decimal = 0) -> bool:
        low = _exact(self.min_cm) - _exact(float(below_cm))
        high = _exact(self.max_cm) + _exact(float(above_cm))
        return low <= _exact(cm) <= high

    def distance_to(self, cm: float) -> Decimal:
        value = _exact(cm)
        return max(_exact(self.min_cm) - value, value - _exact(self.max_cm), Decimal(0))

    def gap_to(self, other: "Interval") -> Decimal:
        """Empty space between two intervals. Touching or overlapping intervals have none."""
        return max(
            _exact(other.min_cm) - _exact(self.max_cm), _exact(self.min_cm) - _exact(other.max_cm), Decimal(0)
        )

    def overlaps_beyond_touching(self, other: "Interval") -> bool:
        return max(self.min_cm, other.min_cm) < min(self.max_cm, other.max_cm)

    @property
    def text(self) -> str:
        if self.is_point:
            return f"{self.min_cm:g} cm"
        return f"{self.min_cm:g}–{self.max_cm:g} cm"  # noqa: RUF001


@dataclass(frozen=True)
class ChartSize:
    label: str
    ranges: Mapping[Dimension, Interval]


@dataclass(frozen=True)
class FitChart:
    sizes: tuple[ChartSize, ...]

    def size(self, label: str) -> ChartSize | None:
        return next((s for s in self.sizes if s.label == label), None)

    def lists(self, dimension: Dimension) -> bool:
        return any(dimension in s.ranges for s in self.sizes)

    def offered(self, labels: tuple[str, ...]) -> tuple[ChartSize, ...]:
        """The chart's sizes a store sells. With no list from the store, every size counts."""
        return self.sizes if not labels else tuple(s for s in self.sizes if s.label in labels)


def _interval(measure: Measure) -> Interval:
    low = measure.cm if measure.min_cm is None else measure.min_cm
    high = measure.cm if measure.max_cm is None else measure.max_cm
    return Interval(low, high, measure.basis)


def _ranges(row: SizeRow) -> dict[Dimension, Interval]:
    known = {d.value: d for d in Dimension}
    return {known[d]: _interval(m) for d, m in row.measures.items() if d in known}


def _length_variants(extract: ProductExtract) -> dict[str, list[int]]:
    """Lengths sold per waist label: "26x30" and "26x32" give {"26": [30, 32]}."""
    lengths: dict[str, set[int]] = {}
    for label in extract.sizes:
        if (parsed := parse_size_label(label)) and parsed[1]:
            lengths.setdefault(parsed[0], set()).add(parsed[1])
    return {waist: sorted(values) for waist, values in lengths.items()}


def _with_lengths(row: SizeRow, waist: str, lengths: list[int]) -> list[ChartSize]:
    ranges = _ranges(row)
    # A length label states the garment's inseam, so it can only be compared with garment values.
    return [
        ChartSize(
            f"{waist}x{length}",
            {**ranges, Dimension.INSEAM: _inseam_interval(length)},
        )
        for length in lengths
    ]


def _inseam_interval(length_in: int) -> Interval:
    cm = float(round(length_in * CM_PER_IN, 1))
    return Interval(cm, cm, Basis.GARMENT)


def _waist_label(label: str) -> str:
    parsed = parse_size_label(label)
    return parsed[0] if parsed else label


def _row_sizes(row: SizeRow, lengths: dict[str, list[int]]) -> list[ChartSize]:
    waist = _waist_label(row.label)
    if waist in lengths and "inseam" not in row.measures:
        return _with_lengths(row, waist, lengths[waist])
    return [ChartSize(row.label, _ranges(row))]


def chart_from_extract(extract: ProductExtract) -> tuple[FitChart | None, tuple[str, ...]]:
    """A page's chart with length variants expanded, plus the labels the store sells."""
    if not extract.size_chart:
        return None, tuple(extract.sizes)
    lengths = _length_variants(extract)
    sold = {_waist_label(s) for s in extract.sizes}
    sizes = [size for row in extract.size_chart.rows for size in _row_sizes(row, lengths)]
    labels = tuple(s.label for s in sizes if _waist_label(s.label) in sold)
    # Sizes the chart doesn't describe stay as listed: they match nothing, so nothing is compared.
    return FitChart(tuple(sizes)), labels or tuple(extract.sizes)
