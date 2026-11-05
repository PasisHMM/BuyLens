from pydantic import BaseModel

from app.pipeline.measurements import CATEGORY_RULES, DIMENSIONS
from app.pipeline.models import Dimension, FitCategory, QuickSize, SizeSystem


class DimensionOut(BaseModel):
    id: Dimension
    label: str
    min_cm: float
    max_cm: float


class CategoryOut(BaseModel):
    id: FitCategory
    label: str
    critical: list[Dimension]
    secondary: list[Dimension]


class Catalog(BaseModel):
    """What can be measured and which rules apply. Web forms read this and keep no copy of their own."""

    dimensions: list[DimensionOut]
    categories: list[CategoryOut]
    quick_sizes: list[QuickSize]
    size_systems: list[SizeSystem]


def build_catalog() -> Catalog:
    in_order = list(Dimension)  # frozensets have no order; the enum gives one stable order
    return Catalog(
        dimensions=[
            DimensionOut(id=d, label=spec.label, min_cm=spec.plausible_cm[0], max_cm=spec.plausible_cm[1])
            for d, spec in DIMENSIONS.items()
        ],
        categories=[
            CategoryOut(
                id=category,
                label=category.value.capitalize(),
                critical=[d for d in in_order if d in rule.critical],
                secondary=[d for d in in_order if d in rule.secondary],
            )
            for category, rule in CATEGORY_RULES.items()
        ],
        quick_sizes=list(QuickSize),
        size_systems=list(SizeSystem),
    )
