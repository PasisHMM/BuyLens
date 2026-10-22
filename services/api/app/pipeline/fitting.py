"""Size choice and Fit Check. Pure functions, no LLM: the same inputs always give the same card."""

from uuid import UUID

from app.pipeline.extract.attributes import BOTTOMS, parse_size_label, size_display
from app.pipeline.models import (
    DIMENSION_NOUN,
    FitCheck,
    FitMatch,
    FitRow,
    Measure,
    MemorySnapshot,
    ProductExtract,
    ProfileSnapshot,
    SizeChoice,
    SizeRow,
)

IN = 2.54
# Acceptable (chart - you) in cm. Garment charts need ease; body charts should match the body.
RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "garment": {"waist": (0.0, 1.5 * IN), "hips": (0.5 * IN, 3.0 * IN), "inseam": (-0.5 * IN, 0.5 * IN)},
    "body": {"waist": (-0.5 * IN, 1.0 * IN), "hips": (-0.5 * IN, 1.5 * IN), "inseam": (-0.5 * IN, 0.5 * IN)},
}
STRETCH_BONUS = 1.0 * IN  # stretch fabric tolerates a tighter garment (circumferences only)
DIMENSION_ORDER = ("waist", "inseam", "hips")


def _range(dim: str, basis: str, stretch: bool, memory_cm: float) -> tuple[float, float]:
    lo, hi = RANGES[basis][dim]
    lo += memory_cm  # learned from feedback: + means "needs more room"
    if stretch and basis == "garment" and dim != "inseam":
        lo -= STRETCH_BONUS
    return lo, hi


def _expand_rows(extract: ProductExtract) -> list[SizeRow]:
    """Chart rows, combined with length variants (e.g. 26x30) that fix the garment inseam."""
    chart_rows = extract.size_chart.rows if extract.size_chart else []
    lengths: dict[str, set[int]] = {}
    for label in extract.sizes:
        if (parsed := parse_size_label(label)) and parsed[1]:
            lengths.setdefault(parsed[0], set()).add(parsed[1])

    # Only sizes the store actually sells (when it lists them).
    offered = {p[0] if (p := parse_size_label(s)) else s for s in extract.sizes}

    rows: list[SizeRow] = []
    for row in chart_rows:
        parsed = parse_size_label(row.label)
        waist_label = parsed[0] if parsed else None
        if offered and (waist_label or row.label) not in offered:
            continue
        if waist_label and waist_label in lengths and "inseam" not in row.measures:
            for length in sorted(lengths[waist_label]):
                measures = {**row.measures, "inseam": Measure(cm=round(length * IN, 1), basis="garment")}
                rows.append(SizeRow(label=f"{waist_label}x{length}", measures=measures))
        else:
            rows.append(row)
    return rows


def choose_size(extract: ProductExtract, profile: ProfileSnapshot, memory: MemorySnapshot,
                brand_id: UUID | None) -> SizeChoice | None:  # fmt: skip
    """The chart row closest to the middle of every acceptable range."""
    stretch = bool(extract.attributes.get("stretch"))
    best: tuple[float, SizeRow] | None = None
    for row in _expand_rows(extract):
        if "waist" not in row.measures:
            continue
        cost = 0.0
        for dim, user_cm in profile.measurements_cm.items():
            measure = row.measures.get(dim)
            if measure is None:
                continue
            lo, hi = _range(dim, measure.basis, stretch, memory.ease_adjust(brand_id, extract.category, dim))
            room = measure.cm - user_cm
            outside = max(lo - room, room - hi, 0.0)
            cost += outside * 10 + abs(room - (lo + hi) / 2)
        if best is None or cost < best[0]:
            best = (cost, row)
    if best is None:
        return None
    row = best[1]
    return SizeChoice(label=row.label, display=size_display(row.label), row=row)


def _classify(dim: str, room: float, lo: float, hi: float) -> FitMatch:
    if room < lo:
        return FitMatch.SHORT if dim == "inseam" else FitMatch.TIGHT
    if room > hi:
        return FitMatch.LONG if dim == "inseam" else FitMatch.LOOSE
    return FitMatch.OK


def _fmt_in(cm: float) -> str:
    return f'{cm / IN:.1f}"'.replace('.0"', '"')


def evaluate_fit(extract: ProductExtract, size: SizeChoice | None, profile: ProfileSnapshot,
                 memory: MemorySnapshot, brand_id: UUID | None,
                 fit_signal: str = "unknown") -> FitCheck:  # fmt: skip
    stretch = extract.attributes.get("stretch")
    measures = size.row.measures if size and size.row else {}
    rows: list[FitRow] = []
    alerts: list[str] = []
    notes: list[str] = []

    if extract.category not in BOTTOMS:
        alerts.append("Fit check covers jeans, pants, shorts and skirts for now.")
    elif not extract.size_chart:
        alerts.append("No size chart found")

    dims = [d for d in DIMENSION_ORDER if d in profile.measurements_cm]
    for dim in dims:
        user_cm = profile.measurements_cm[dim]
        measure = measures.get(dim)
        if measure is None:
            rows.append(FitRow(dimension=dim, user_cm=user_cm, garment_cm=None, basis=None,
                               match=FitMatch.MISSING, room_cm=None))  # fmt: skip
            if extract.size_chart:
                alerts.append(f"{DIMENSION_NOUN.get(dim, dim).capitalize()} measurement unavailable")
            continue
        lo, hi = _range(
            dim, measure.basis, bool(stretch), memory.ease_adjust(brand_id, extract.category, dim)
        )
        room = round(measure.cm - user_cm, 1)
        match = _classify(dim, room, lo, hi)
        rows.append(FitRow(dimension=dim, user_cm=user_cm, garment_cm=measure.cm, basis=measure.basis,
                           match=match, room_cm=room))  # fmt: skip
        if dim == "inseam":
            notes.append("inseam matches" if match is FitMatch.OK else f"inseam runs {match.value}")
        elif match is FitMatch.OK and measure.basis == "garment":
            notes.append(f"{DIMENSION_NOUN.get(dim, dim)} allows {_fmt_in(room)} ease")
        elif match is FitMatch.OK:
            notes.append(f"{DIMENSION_NOUN.get(dim, dim)} matches the size chart")
        else:
            side = "short of" if room < 0 else "over"
            notes.append(
                f"{DIMENSION_NOUN.get(dim, dim)} likely {match.value} ({_fmt_in(abs(room))} {side} the range)"
            )

    fabric = extract.attributes.get("fabric")
    if fabric:
        notes.append(str(fabric))
    if stretch is False:
        notes.append("no stretch")
    elif stretch:
        notes.append("stretch fabric")
    if fit_signal in ("runs_small", "runs_large"):
        notes.append(f"reviews say it {fit_signal.replace('_', ' ')}")

    missing = [r.dimension for r in rows if r.match is FitMatch.MISSING]
    if not rows or len(missing) == len(rows):
        confidence = "limited"
    elif missing == ["inseam"]:
        confidence = "medium"
    elif missing:
        confidence = "limited"
    else:
        confidence = "high"
    if confidence == "high" and fit_signal in ("runs_small", "runs_large"):
        confidence = "medium"

    sentence = "; ".join(notes)
    return FitCheck(
        size_label=size.display if size else "—",
        rows=rows,
        confidence=confidence,
        alerts=alerts,
        notes=(sentence[:1].upper() + sentence[1:] + ".") if sentence else "",
    )
