"""LLM fallback extraction from cleaned page text.

The model may only *read* the page: every number it returns must literally appear in the
page text, otherwise it is dropped. This is what keeps "Hip measurement unavailable"
honest instead of a plausible-looking invented value.
"""

from typing import Literal

from pydantic import BaseModel

from app.llm import LLM, LLMError
from app.pipeline.extract.text import number_in_text, to_cents
from app.pipeline.models import Measure, ProductExtract, SizeChart, SizeRow

CM_PER_IN = 2.54
MAX_PAGE_CHARS = 150_000  # ≈ 40k tokens

SYSTEM = """You extract facts from an online clothing product page for a shopping assistant.
Rules:
- Copy facts exactly as written on the page. Never estimate, convert, or fill in typical values.
- Return null (or an empty list) for anything the page does not state explicitly.
- Size chart: copy numbers as shown, in the page's unit. If a cell is a range like 26-27, return the midpoint.
- size_chart_basis is "garment" only if the page says the chart measures the garment/product
  (e.g. "garment measurements", "measured flat"); "body" if it measures the wearer; else "unknown".
- price is the current selling price of the default variant, as a number without currency symbols."""


class LLMSizeRow(BaseModel):
    label: str
    waist: float | None
    hips: float | None
    inseam: float | None


class LLMProductPage(BaseModel):
    """Kept flat for Gemini's structured-output schema support."""

    is_product_page: bool
    name: str | None
    brand: str | None
    category: str | None
    price: float | None
    currency: str | None
    shipping_price: float | None
    color: str | None
    fabric: str | None
    sizes: list[str]
    size_chart_unit: Literal["in", "cm", "none"]
    size_chart_basis: Literal["body", "garment", "unknown"]
    size_chart: list[LLMSizeRow]
    review_rating: float | None
    review_count: int | None


def _verified(value: float | None, text: str) -> float | None:
    return value if value is not None and number_in_text(value, text) else None


def _chart(page: LLMProductPage, text: str) -> SizeChart | None:
    if page.size_chart_unit == "none" or not page.size_chart:
        return None
    basis = "garment" if page.size_chart_basis == "garment" else "body"
    factor = CM_PER_IN if page.size_chart_unit == "in" else 1.0
    rows = []
    for row in page.size_chart:
        measures = {
            dim: Measure(cm=round(v * factor, 1), basis=basis)
            for dim in ("waist", "hips", "inseam")
            if (v := _verified(getattr(row, dim), text)) is not None
        }
        if measures:
            rows.append(SizeRow(label=row.label.strip(), measures=measures))
    return SizeChart(rows=rows, source="llm") if len(rows) >= 2 else None


async def llm_extract(llm: LLM, text: str, base: ProductExtract) -> ProductExtract:
    """Fill the gaps in `base` from the page text. Facts already found structurally win."""
    text = text[:MAX_PAGE_CHARS]
    try:
        page = await llm.structured(
            tier="fast",
            system=SYSTEM,
            prompt=f'<page url="{base.url}">\n{text}\n</page>',
            schema=LLMProductPage,
            max_tokens=2048,
        )
    except LLMError:
        return base
    if not page.is_product_page:
        return base

    out = base.model_copy(deep=True)
    out.name = out.name or (page.name or "").strip()
    out.brand = out.brand or page.brand
    out.category = out.category or page.category
    out.color = out.color or page.color
    if not out.price_cents and (price := _verified(page.price, text)):
        out.price_cents = to_cents(price) or 0
        out.currency = (page.currency or out.currency).upper()[:3]
    if out.shipping_cents is None and (ship := _verified(page.shipping_price, text)) is not None:
        out.shipping_cents = to_cents(ship)
    if page.fabric and "fabric" not in out.attributes:
        out.attributes["fabric"] = page.fabric
    out.sizes = out.sizes or [s.strip() for s in page.sizes if s.strip()]
    out.size_chart = out.size_chart or _chart(page, text)
    if out.review_rating is None:
        out.review_rating = _verified(page.review_rating, text)
    if (
        out.review_count is None
        and page.review_count
        and number_in_text(page.review_count, text.replace(",", ""))
    ):
        out.review_count = page.review_count
    out.extracted_by.append("llm")
    return out
