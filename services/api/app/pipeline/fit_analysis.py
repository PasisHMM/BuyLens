"""Fit analysis: MATCH / UNCERTAIN / MISMATCH. Pure functions: the same inputs always give the same result.

Rules are in docs/redesign-plan.md §2.3. Missing data never counts against a product, and nothing is
filled in with a guess. Quick Fit compares published ranges with each other and never derives a number
for the person; §2.2 lists the only proof that lets it return MISMATCH.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.pipeline.extract.attributes import size_display
from app.pipeline.fit_profile import Measurement
from app.pipeline.measurements import CategoryRule, rule_for
from app.pipeline.models import (
    Basis,
    Dimension,
    DimensionStatus,
    FitCategory,
    FitCheck,
    FitMode,
    FitOutcome,
    FitRow,
    ProductExtract,
    ProfileSnapshot,
    QuickSize,
)
from app.pipeline.size_charts import ChartSize, FitChart, Interval, chart_from_extract
from app.pipeline.taxonomy import fit_category_for, no_fit_rules_reason

# Stretch fabric tolerates a tighter garment. It can only turn a garment mismatch into UNCERTAIN.
STRETCH_ALLOWANCE_CM = 2.54
_CIRCUMFERENCES = frozenset({Dimension.CHEST, Dimension.WAIST, Dimension.HIPS})
_NO_CHART = "No size chart was found for this product."
_UNKNOWN_SIZES = "The sizes listed for this product aren't in its size chart, so they can't be compared."

Measurements = Mapping[Dimension, Measurement]


def _name(dimension: Dimension) -> str:
    return dimension.value.capitalize()


def _labels(sizes: list[ChartSize]) -> str | None:
    return " / ".join(size_display(s.label) for s in sizes) or None


def _result(
    mode: FitMode,
    outcome: FitOutcome,
    reasons: list[str],
    sizes: list[ChartSize] | None = None,
    rows: list[FitRow] | None = None,
) -> FitCheck:
    return FitCheck(
        mode=mode,
        outcome=outcome,
        approximate=mode is FitMode.QUICK_FIT,
        size_label=_labels(sizes or []),
        rows=rows or [],
        reasons=reasons,
    )


def _in_order(dimensions: frozenset[Dimension]) -> list[Dimension]:
    return [d for d in Dimension if d in dimensions]


# ── Personal Fit ──


@dataclass(frozen=True)
class _Comparison:
    rule: CategoryRule
    mine: Measurements
    stretch: bool

    def comparable(self, size: ChartSize, dimension: Dimension) -> Interval | None:
        interval = size.ranges.get(dimension)
        mine = self.mine.get(dimension)
        return interval if interval and mine and interval.basis is mine.basis else None

    def tolerance(self, interval: Interval) -> float:
        return self.rule.tolerance_cm(interval.basis)

    def status(self, size: ChartSize, dimension: Dimension) -> DimensionStatus:
        interval = self.comparable(size, dimension)
        if interval is None:
            return DimensionStatus.MISSING
        cm = self.mine[dimension].value_cm
        tolerance = self.tolerance(interval)
        if interval.covers(cm, tolerance, tolerance) if interval.is_point else interval.covers(cm):
            return DimensionStatus.INSIDE
        allowance = self._stretch_allowance(dimension, interval)
        return (
            DimensionStatus.NEAR
            if interval.covers(cm, tolerance, tolerance + allowance)
            else DimensionStatus.OUTSIDE
        )

    def _stretch_allowance(self, dimension: Dimension, interval: Interval) -> float:
        applies = self.stretch and interval.basis is Basis.GARMENT and dimension in _CIRCUMFERENCES
        return STRETCH_ALLOWANCE_CM if applies else 0.0

    def critical_statuses(self, size: ChartSize) -> list[DimensionStatus]:
        return [self.status(size, d) for d in self.rule.critical]

    def is_inside(self, size: ChartSize) -> bool:
        known = [s for s in self.critical_statuses(size) if s is not DimensionStatus.MISSING]
        return bool(known) and all(s is DimensionStatus.INSIDE for s in known)

    def is_outside(self, size: ChartSize) -> bool:
        return DimensionStatus.OUTSIDE in self.critical_statuses(size)

    def is_near(self, size: ChartSize) -> bool:
        return DimensionStatus.NEAR in self.critical_statuses(size) and not self.is_outside(size)

    def distance(self, size: ChartSize, dimensions: frozenset[Dimension]) -> Decimal:
        return sum(
            (
                interval.distance_to(self.mine[d].value_cm)
                for d in dimensions
                if (interval := self.comparable(size, d))
            ),
            start=Decimal(),
        )

    def signature(self, size: ChartSize) -> tuple[Interval | None, ...]:
        """Length variants of one size share this, so they never count as competing sizes."""
        return tuple(self.comparable(size, d) for d in _in_order(self.rule.critical))

    def rows(self, size: ChartSize) -> list[FitRow]:
        return [
            self._row(size, d, role)
            for role, group in (("critical", self.rule.critical), ("secondary", self.rule.secondary))
            for d in _in_order(group)
        ]

    def _row(self, size: ChartSize, dimension: Dimension, role: str) -> FitRow:
        interval = size.ranges.get(dimension)
        mine = self.mine.get(dimension)
        return FitRow(
            dimension=dimension.value,
            role=role,
            user_cm=mine.value_cm if mine else None,
            chart_min_cm=interval.min_cm if interval else None,
            chart_max_cm=interval.max_cm if interval else None,
            basis=interval.basis if interval else None,
            status=self.status(size, dimension),
        )

    def critical_gaps(self, size: ChartSize) -> list[str]:
        """What the comparison lacks, in words."""
        return [self._gap(size, d) for d in _in_order(self.rule.critical) if not self.comparable(size, d)]

    def _gap(self, size: ChartSize, dimension: Dimension) -> str:
        interval = size.ranges.get(dimension)
        mine = self.mine.get(dimension)
        if interval is None:
            return f"The size chart doesn't list {dimension.value}."
        if mine is None:
            return f"Add your {dimension.value} measurement."
        return (
            f"Your {dimension.value} is a {mine.basis.value} measurement and this chart lists "
            f"{interval.basis.value} measurements, so they can't be compared."
        )

    def unchecked_secondary(self, size: ChartSize) -> list[str]:
        return [d.value for d in _in_order(self.rule.secondary) if not self.comparable(size, d)]

    def secondary_concerns(self, size: ChartSize) -> list[str]:
        return [
            f"{_name(d)} {self.mine[d].value_cm:g} cm doesn't match size {size_display(size.label)} "
            f"({size.ranges[d].text}). This is an additional measurement, so check it before buying."
            for d in _in_order(self.rule.secondary)
            if self.status(size, d) is DimensionStatus.OUTSIDE
        ]

    def outside_reasons(self, size: ChartSize, closest: bool) -> list[str]:
        where = f"size {size_display(size.label)}" + (", the closest listed size" if closest else "")
        return [
            f"{_name(d)} {self.mine[d].value_cm:g} cm is outside {where} "
            f"({size.ranges[d].text}), beyond the ±{self.tolerance(size.ranges[d]):g} cm tolerance."
            for d in _in_order(self.rule.critical)
            if self.status(size, d) is DimensionStatus.OUTSIDE
        ]


def _nearest_if_points(check: _Comparison, inside: list[ChartSize]) -> list[ChartSize]:
    """Single published values have no range, so the closest one stands for the person's size."""
    points = [all(i.is_point for d in check.rule.critical if (i := check.comparable(s, d))) for s in inside]
    if not inside or not all(points):
        return inside
    best = min(check.distance(s, check.rule.critical) for s in inside)
    return [s for s in inside if check.distance(s, check.rule.critical) == best]


def _ambiguity_reason(check: _Comparison, sizes: list[ChartSize]) -> str:
    first, second = sizes[0], sizes[1]
    for dimension in _in_order(check.rule.critical):
        low, high = check.comparable(first, dimension), check.comparable(second, dimension)
        if low and high and low != high:
            cm = check.mine[dimension].value_cm
            return (
                f"{_name(dimension)} {cm:g} cm fits both size {size_display(first.label)} ({low.text}) "
                f"and size {size_display(second.label)} ({high.text}), so the right size isn't clear."
            )
    return "More than one size fits these measurements."  # sizes differ only where nothing was compared


def _inside_result(check: _Comparison, published: list[ChartSize], offered: list[ChartSize]) -> FitCheck:
    mode = FitMode.PERSONAL_FIT
    if len({check.signature(s) for s in published}) > 1:
        reason = _ambiguity_reason(check, published)
        return _result(mode, FitOutcome.UNCERTAIN, [reason], offered, check.rows(offered[0]))
    size = min(offered, key=lambda s: check.distance(s, check.rule.secondary))
    gaps = check.critical_gaps(size)
    concerns = check.secondary_concerns(size)
    if concerns or gaps:
        return _result(mode, FitOutcome.UNCERTAIN, concerns + gaps, [size], check.rows(size))
    reasons = [f"Your measurements are inside size {size_display(size.label)}."]
    if unchecked := check.unchecked_secondary(size):
        reasons.append(f"Not checked: {', '.join(unchecked)}.")
    return _result(mode, FitOutcome.MATCH, reasons, [size], check.rows(size))


def _outside_result(check: _Comparison, offered: tuple[ChartSize, ...]) -> FitCheck:
    mode = FitMode.PERSONAL_FIT
    closest = min(offered, key=lambda s: check.distance(s, check.rule.critical))
    near = [s for s in offered if check.is_near(s)]
    if near:
        size = min(near, key=lambda s: check.distance(s, check.rule.critical))
        reason = (
            f"Your measurements are just outside size {size_display(size.label)}, "
            "within the tolerance, so check the fit before buying."
        )
        return _result(
            mode, FitOutcome.UNCERTAIN, [reason, *check.critical_gaps(size)], [size], check.rows(size)
        )
    if all(check.is_outside(s) for s in offered):
        reasons = check.outside_reasons(closest, closest=len(offered) > 1)
        return _result(mode, FitOutcome.MISMATCH, reasons, rows=check.rows(closest))
    # Some listed sizes have nothing to compare, so no size can be ruled out for all of them.
    return _result(mode, FitOutcome.UNCERTAIN, check.critical_gaps(closest), rows=check.rows(closest))


def personal_fit(
    product_type: str | None,
    chart: FitChart | None,
    offered_labels: tuple[str, ...],
    measurements: Measurements,
    *,
    stretch: bool = False,
) -> FitCheck:
    """Compare exact measurements with the published ranges of the sizes a store sells."""
    mode = FitMode.PERSONAL_FIT
    category = fit_category_for(product_type)
    if category is None:
        return _result(mode, FitOutcome.UNCERTAIN, [no_fit_rules_reason(product_type)])
    if chart is None:
        return _result(mode, FitOutcome.UNCERTAIN, [_NO_CHART])
    offered = chart.offered(offered_labels)
    if not offered:
        return _result(mode, FitOutcome.UNCERTAIN, [_UNKNOWN_SIZES])

    check = _Comparison(rule_for(category), measurements, stretch)
    if not any(check.comparable(s, d) for s in offered for d in check.rule.critical):
        return _result(
            mode, FitOutcome.UNCERTAIN, check.critical_gaps(offered[0]), rows=check.rows(offered[0])
        )
    # Ambiguity looks at every published size: a person on the S/M line may need M even if only S is sold.
    published = _nearest_if_points(check, [s for s in chart.sizes if check.is_inside(s)])
    inside_offered = [s for s in published if s in offered]
    if inside_offered:
        return _inside_result(check, published, inside_offered)
    return _outside_result(check, offered)


# ── Quick Fit ──


def _gap_proof(
    reference: ChartSize, offered: tuple[ChartSize, ...], dimensions: list[Dimension], rule: CategoryRule
) -> str | None:
    """A priority range of the chosen size that no sold size comes near: the only proof of a mismatch."""
    for dimension in dimensions:
        mine = reference.ranges.get(dimension)
        others = [s.ranges.get(dimension) for s in offered]
        if mine is None or None in others:
            continue
        ranges = [o for o in others if o is not None]
        if all(mine.gap_to(o) > Decimal(str(rule.tolerance_cm(o.basis))) for o in ranges):
            closest = min(offered, key=lambda s: mine.gap_to(s.ranges[dimension]))
            return (
                f"{_name(dimension)} for size {size_display(reference.label)} is {mine.text}. "
                f"The closest listed size, {size_display(closest.label)}, "
                f"is {closest.ranges[dimension].text}, "
                "too far apart for any measurement in your size to fit."
            )
    return None


def _quick_rows(size: ChartSize, dimensions: list[Dimension]) -> list[FitRow]:
    rows = []
    for dimension in dimensions:
        interval = size.ranges.get(dimension)
        rows.append(
            FitRow(
                dimension=dimension.value,
                role="critical",
                user_cm=None,  # Quick Fit never derives a measurement from a size label
                chart_min_cm=interval.min_cm if interval else None,
                chart_max_cm=interval.max_cm if interval else None,
                basis=interval.basis if interval else None,
                status=DimensionStatus.INSIDE if interval else DimensionStatus.MISSING,
            )
        )
    return rows


def _overlapping(reference: ChartSize, chart: FitChart, dimensions: list[Dimension]) -> ChartSize | None:
    for other in chart.sizes:
        if other.label == reference.label:
            continue
        for dimension in dimensions:
            mine, theirs = reference.ranges.get(dimension), other.ranges.get(dimension)
            if mine and theirs and mine.overlaps_beyond_touching(theirs):
                return other
    return None


def _quick_listed_size(reference: ChartSize, chart: FitChart, dimensions: list[Dimension]) -> FitCheck:
    mode = FitMode.QUICK_FIT
    rows = _quick_rows(reference, dimensions)
    missing = [d for d in dimensions if d not in reference.ranges]
    gaps = [f"The size chart doesn't list {d.value}." for d in missing]
    label = size_display(reference.label)
    if gaps:
        return _result(mode, FitOutcome.UNCERTAIN, gaps, [reference], rows)
    if other := _overlapping(reference, chart, dimensions):
        reason = (
            f"Size {label} overlaps size {size_display(other.label)}, so your size alone can't settle it."
        )
        return _result(mode, FitOutcome.UNCERTAIN, [reason], [reference], rows)
    names = " and ".join(d.value for d in dimensions)
    reason = f"Approximate fit based on size {label}. The size chart publishes {names} for this size."
    return _result(mode, FitOutcome.MATCH, [reason], [reference], rows)


def quick_fit(
    product_type: str | None,
    chart: FitChart | None,
    offered_labels: tuple[str, ...],
    sizes: Mapping[FitCategory, QuickSize],
) -> FitCheck:
    """Compare the chosen size's published ranges with what a store sells. Always approximate."""
    mode = FitMode.QUICK_FIT
    category = fit_category_for(product_type)
    if category is None:
        return _result(mode, FitOutcome.UNCERTAIN, [no_fit_rules_reason(product_type)])
    size = sizes.get(category)
    if size is None:
        return _result(mode, FitOutcome.UNCERTAIN, [f"Add your {category.value.capitalize()} size."])
    if chart is None:
        return _result(mode, FitOutcome.UNCERTAIN, [_NO_CHART])
    offered = chart.offered(offered_labels)
    if not offered:
        return _result(mode, FitOutcome.UNCERTAIN, [_UNKNOWN_SIZES])
    reference = chart.size(size.value)
    if reference is None:
        return _result(mode, FitOutcome.UNCERTAIN, [f"The size chart doesn't describe size {size.value}."])

    rule = rule_for(category)
    dimensions = _in_order(rule.quick_fit_dimensions)
    if reference in offered:
        return _quick_listed_size(reference, chart, dimensions)
    if proof := _gap_proof(reference, offered, dimensions, rule):
        return _result(mode, FitOutcome.MISMATCH, [proof], rows=_quick_rows(reference, dimensions))
    reason = f"This product isn't listed in size {size.value}, and a listed size might still fit."
    return _result(mode, FitOutcome.UNCERTAIN, [reason], rows=_quick_rows(reference, dimensions))


# ── From a product page ──


def _measurements(profile: ProfileSnapshot) -> dict[Dimension, Measurement]:
    known = {d.value: d for d in Dimension}
    body = {known[d]: Measurement(v) for d, v in profile.measurements_cm.items() if d in known}
    garment = {known[d]: Measurement(v, Basis.GARMENT) for d, v in profile.garment_cm.items() if d in known}
    return {**body, **garment}


def evaluate_offer(extract: ProductExtract, profile: ProfileSnapshot) -> FitCheck:
    chart, offered = chart_from_extract(extract)
    if profile.fit_mode is FitMode.QUICK_FIT:
        return quick_fit(extract.category, chart, offered, profile.quick_sizes)
    # Stretch counts only when the fabric is known (§2.2).
    stretch = bool(extract.attributes.get("stretch") and extract.attributes.get("fabric"))
    return personal_fit(extract.category, chart, offered, _measurements(profile), stretch=stretch)
