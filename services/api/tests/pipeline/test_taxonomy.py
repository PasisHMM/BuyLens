"""Product types: the controlled vocabulary and its fit-category map (docs/redesign-plan.md §2.9)."""

import pytest

from app.pipeline.models import FitCategory
from app.pipeline.taxonomy import (
    PRODUCT_TYPES,
    ProductType,
    fit_category_for,
    infer_product_type,
    no_fit_rules_reason,
)


def test_the_mvp_has_exactly_eight_product_types() -> None:
    assert {t.value for t in ProductType} == {
        "jeans",
        "pants",
        "sweaters",
        "tops",
        "hoodies",
        "skirts",
        "shorts",
        "hats",
    }
    assert set(PRODUCT_TYPES) == set(ProductType)


@pytest.mark.parametrize(
    ("product_type", "category"),
    [
        ("jeans", FitCategory.BOTTOMS),
        ("pants", FitCategory.BOTTOMS),
        ("sweaters", FitCategory.TOPS),
        ("tops", FitCategory.TOPS),
        ("hoodies", FitCategory.TOPS),
        ("skirts", None),
        ("shorts", None),
        ("hats", None),
        ("dresses", None),
        ("outerwear", None),
        ("swimwear", None),
        (None, None),
    ],
)
def test_each_type_maps_to_a_fit_category_or_to_none(
    product_type: str | None, category: FitCategory | None
) -> None:
    assert fit_category_for(product_type) is category


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Women's Jeans", "jeans"),
        ("Denim 501", "jeans"),
        ("Wide-leg trousers", "pants"),
        ("Merino sweater", "sweaters"),
        ("Zip hoodie", "hoodies"),
        ("Long cardigan", "tops"),
        ("Short sleeve shirt", "tops"),
        ("Denim shorts", "jeans"),
        ("Cargo shorts", "shorts"),
        ("Pleated skirt", "skirts"),
        ("Wool beanie", "hats"),
        ("Bucket hat", "hats"),
        ("Baseball cap", "hats"),
        ("Summer dress", "dresses"),
        ("Rain jacket", "outerwear"),
        ("Hatchback", None),
        ("Capri sun", None),
        ("Gift card", None),
    ],
)
def test_keywords_resolve_to_one_controlled_value(text: str, expected: str | None) -> None:
    assert infer_product_type(text) == expected


def test_reasons_explain_why_there_is_no_fit_result() -> None:
    assert no_fit_rules_reason("skirts") == "No fit rules for this product type yet."
    assert no_fit_rules_reason("dresses") == "Not supported in the MVP."
    assert no_fit_rules_reason(None) == "No fit rules for this product type yet."
