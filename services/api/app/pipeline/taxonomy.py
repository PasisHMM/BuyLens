"""Product types: the controlled vocabulary and which fit rules each one uses (docs/redesign-plan.md §2.9).

A type describes what the product is. Whether it fits is decided only from measurements.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.pipeline.models import FitCategory


class ProductType(StrEnum):
    JEANS = "jeans"
    PANTS = "pants"
    SWEATERS = "sweaters"
    TOPS = "tops"  # tops and cardigans
    HOODIES = "hoodies"
    SKIRTS = "skirts"
    SHORTS = "shorts"
    HATS = "hats"


@dataclass(frozen=True)
class ProductTypeSpec:
    label: str
    fit_category: FitCategory | None  # None: no approved fit rules yet


PRODUCT_TYPES: Mapping[ProductType, ProductTypeSpec] = {
    ProductType.JEANS: ProductTypeSpec("Jeans", FitCategory.BOTTOMS),
    ProductType.PANTS: ProductTypeSpec("Pants", FitCategory.BOTTOMS),
    ProductType.SWEATERS: ProductTypeSpec("Sweaters", FitCategory.TOPS),
    ProductType.TOPS: ProductTypeSpec("Tops / cardigans", FitCategory.TOPS),
    ProductType.HOODIES: ProductTypeSpec("Hoodies", FitCategory.TOPS),
    ProductType.SKIRTS: ProductTypeSpec("Skirts", None),
    ProductType.SHORTS: ProductTypeSpec("Shorts", None),
    ProductType.HATS: ProductTypeSpec("Hats", None),
}

# Recognized so they aren't mistaken for another type. They keep their rules in measurements.py,
# but aren't MVP product types.
OUTSIDE_MVP = ("dresses", "outerwear")

# First match wins, so "denim shorts" stay jeans, and "short sleeve shirt" isn't shorts.
_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jeans", (r"jean", r"denim")),
    ("shorts", (r"shorts",)),
    ("skirts", (r"skirt",)),
    ("pants", (r"pant", r"trouser", r"chino", r"slack", r"legging", r"jogger")),
    ("dresses", (r"dress",)),
    ("hoodies", (r"hoodie",)),
    ("sweaters", (r"sweater", r"pullover", r"jumper")),
    ("tops", (r"shirt", r"tee", r"t-shirt", r"top", r"blouse", r"cardigan", r"knit")),
    ("outerwear", (r"jacket", r"coat", r"blazer", r"parka")),
    ("hats", (r"hats?\b", r"beanies?\b", r"caps?\b", r"berets?\b", r"fedoras?\b")),
)


def infer_product_type(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    for product_type, patterns in _KEYWORDS:
        if any(re.search(rf"\b{p}", blob) for p in patterns):
            return product_type
    return None


def fit_category_for(product_type: str | None) -> FitCategory | None:
    """The fit rules for a product, or None when no approved rules apply."""
    try:
        return PRODUCT_TYPES[ProductType(product_type or "")].fit_category
    except ValueError:
        return None


def no_fit_rules_reason(product_type: str | None) -> str:
    if product_type in OUTSIDE_MVP:
        return "Not supported in the MVP."
    return "No fit rules for this product type yet."
