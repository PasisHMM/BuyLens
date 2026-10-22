"""Deterministic size-chart parsing from HTML tables.

Handles size-per-row and size-per-column layouts, inch/cm units, ranges ("26-27" → 26.5),
halves ("26½"), and garment charts measured flat (half circumference → doubled).
"""

import re

from bs4 import BeautifulSoup, Tag

from app.pipeline.models import Basis, Measure, SizeChart, SizeRow

CM_PER_IN = 2.54
DIM_ALIASES: dict[str, tuple[str, ...]] = {
    "waist": ("waist",),
    "hips": ("hip", "seat"),
    "inseam": ("inseam", "inside leg", "inner leg", "leg length"),
}
SIZE_HEADERS = ("size", "waist size", "us size", "label")
# Plausible ranges used only to infer an unlabeled unit.
IN_RANGE = {"waist": (18, 60), "hips": (25, 70), "inseam": (20, 40)}
CM_RANGE = {"waist": (45, 155), "hips": (60, 180), "inseam": (50, 100)}

_NUM = r"\d+(?:[.,]\d+)?(?:\s*½|\s+1/2)?"
_RANGE = re.compile(rf"({_NUM})\s*(?:-|–|—|to)\s*({_NUM})")  # noqa: RUF001
_SINGLE = re.compile(_NUM)


def _num(raw: str) -> float:
    raw = raw.strip()
    half = 0.5 if ("½" in raw or "1/2" in raw) else 0.0
    raw = raw.replace("½", "").replace("1/2", "").strip().replace(",", ".")
    return float(raw) + half


def _value(cell: str) -> float | None:
    if m := _RANGE.search(cell):
        return round((_num(m[1]) + _num(m[2])) / 2, 2)
    if m := _SINGLE.search(cell):
        return _num(m[0])
    return None


def _dimension(header: str) -> str | None:
    h = header.lower()
    for dim, aliases in DIM_ALIASES.items():
        if any(a in h for a in aliases):
            return dim
    return None


def _unit(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bcm\b|centimet", t):
        return "cm"
    if re.search(r"\bin\b|\binch|\"|”", t):
        return "in"
    return None


def _context(table: Tag) -> str:
    """Caption plus nearby headings/paragraphs, where charts say 'body' vs 'garment' and the unit."""
    parts = [table.caption.get_text(" ", strip=True)] if table.caption else []
    node: Tag | None = table
    for _ in range(4):
        node = node.find_previous(["h1", "h2", "h3", "h4", "p", "div", "span", "label"]) if node else None
        if node is None:
            break
        parts.append(node.get_text(" ", strip=True)[:300])
    return " ".join(parts)


def _basis(text: str) -> Basis:
    t = text.lower()
    if re.search(r"garment|product measurement|laid flat|measured flat|item measurement", t):
        return "garment"
    return "body"


def _rows(table: Tag) -> list[list[str]]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    return rows


def _to_cm(dim: str, value: float, unit: str | None) -> float | None:
    if unit is None:  # infer only when the ranges are unambiguous
        lo, hi = IN_RANGE[dim]
        clo, chi = CM_RANGE[dim]
        if lo <= value <= hi and not clo <= value <= chi:
            unit = "in"
        elif clo <= value <= chi and not lo <= value <= hi:
            unit = "cm"
        else:
            return None
    return round(value * CM_PER_IN if unit == "in" else value, 1)


def parse_table(table: Tag) -> SizeChart | None:
    rows = _rows(table)
    if len(rows) < 2:
        return None
    context = _context(table)
    basis = _basis(context + " " + " ".join(rows[0]))
    table_unit = _unit(" ".join(rows[0]) + " " + context)

    header = rows[0]
    header_dims = [_dimension(h) for h in header]
    entries: dict[str, dict[str, tuple[float, str | None]]] = {}

    if any(header_dims) and _dimension(header[0]) is None:
        # Size per row: | Size | Waist (in) | Hip (in) | Inseam |
        for row in rows[1:]:
            label = row[0].strip()
            for i, dim in enumerate(header_dims):
                if dim and i < len(row) and (v := _value(row[i])) is not None:
                    entries.setdefault(label, {})[dim] = (v, _unit(header[i]) or table_unit)
    else:
        # Size per column: | | 24 | 25 | 26 |  then  | Waist | 24 | 25 | 26 |
        for row in rows[1:]:
            dim = _dimension(row[0])
            if dim is None:
                continue
            unit = _unit(row[0]) or table_unit
            for i, label in enumerate(header[1:], start=1):
                if i < len(row) and label.strip() and (v := _value(row[i])) is not None:
                    entries.setdefault(label.strip(), {})[dim] = (v, unit)

    size_rows: list[SizeRow] = []
    for label, dims in entries.items():
        if not label or label.lower() in SIZE_HEADERS:
            continue
        measures: dict[str, Measure] = {}
        for dim, (value, unit) in dims.items():
            cm = _to_cm(dim, value, unit)
            if cm is None:
                continue
            if basis == "garment" and dim in ("waist", "hips") and cm < 45:
                cm = round(cm * 2, 1)  # measured flat: half the circumference
            measures[dim] = Measure(cm=cm, basis=basis)
        if measures:
            size_rows.append(SizeRow(label=label, measures=measures))
    return SizeChart(rows=size_rows, source="table") if len(size_rows) >= 2 else None


def find_size_chart(soup: BeautifulSoup) -> SizeChart | None:
    best: SizeChart | None = None
    for table in soup.find_all("table"):
        if not any(_dimension(c) for row in _rows(table)[:3] for c in row[:6]):
            continue
        chart = parse_table(table)
        if chart and (best is None or len(chart.rows) > len(best.rows)):
            best = chart
    return best
