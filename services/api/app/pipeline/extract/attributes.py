"""Deterministic product attributes: category, fabric stretch, fit, and size-label parsing."""

import re

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("jeans", ("jean", "denim")),
    ("shorts", ("shorts",)),  # not "short" — "short sleeve shirt" is a top
    ("skirts", ("skirt",)),
    ("pants", ("pant", "trouser", "chino", "slack", "legging", "jogger")),
    ("dresses", ("dress",)),
    ("tops", ("shirt", "tee", "t-shirt", "top", "blouse", "sweater", "hoodie", "knit")),
    ("outerwear", ("jacket", "coat", "blazer", "parka")),
]
BOTTOMS = {"jeans", "pants", "shorts", "skirts"}

STRETCH_FIBERS = ("elastane", "spandex", "lycra", "elasterell", "t400")
FIT_WORDS = (
    "skinny",
    "slim",
    "straight",
    "relaxed",
    "wide",
    "bootcut",
    "flare",
    "tapered",
    "barrel",
    "mom",
    "boyfriend",
)
WASH_WORDS = ("light wash", "medium wash", "dark wash", "black", "rinse", "raw", "acid wash", "stonewash")


def infer_category(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    for category, words in CATEGORY_KEYWORDS:
        if any(re.search(rf"\b{re.escape(w)}", blob) for w in words):
            return category
    return None


def infer_stretch(fabric: str | None, *texts: str | None) -> bool | None:
    """True/False when the page says so; None when it doesn't (never guessed)."""
    blob = " ".join(t for t in (fabric, *texts) if t).lower()
    if re.search(r"\bnon[- ]?stretch\b|\brigid\b", blob):
        return False
    if any(f in blob for f in STRETCH_FIBERS) or re.search(r"\b(super |high |comfort )?stretch\b", blob):
        return True
    if fabric and re.search(r"\b100\s*%\s*cotton\b", fabric.lower()):
        return False
    return None


def infer_fit(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    return next((w for w in FIT_WORDS if re.search(rf"\b{w}\b", blob)), None)


def infer_wash(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    return next((w for w in WASH_WORDS if w in blob), None)


_WAIST_LENGTH = re.compile(
    # \u00d7 is the multiplication sign some stores use between waist and length.
    r"^\s*W?\s*(?P<waist>\d{2})\s*W?\s*(?:[xX\u00d7/]|\s)\s*L?\s*(?P<length>\d{2})\s*L?\s*$"
)
_SINGLE = re.compile(r"^\s*W?\s*(?P<waist>\d{2})\s*W?\s*$")


def parse_size_label(label: str) -> tuple[str, int | None] | None:
    """'26x30' / 'W26 L30' / '26W x 30L' / '26/30' → ('26', 30); '26' → ('26', None)."""
    if m := _WAIST_LENGTH.match(label):
        return m["waist"], int(m["length"])
    if m := _SINGLE.match(label):
        return m["waist"], None
    return None


def size_display(label: str) -> str:
    parsed = parse_size_label(label)
    if parsed is None:
        return label
    waist, length = parsed
    return f"W{waist} / L{length}" if length else f"W{waist}"
