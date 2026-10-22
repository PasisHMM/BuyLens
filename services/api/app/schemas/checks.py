from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.pipeline.models import FitCheck, PriceCheck, SellerRisk

RunStatus = Literal["queued", "running", "done", "failed", "cancelled"]


class CheckIn(BaseModel):
    url: str = Field(min_length=4, max_length=2048)


class CheckCreated(BaseModel):
    id: UUID
    status: RunStatus


class CheckSummary(BaseModel):
    """The "A recent check" card."""

    id: UUID
    status: RunStatus
    created_at: datetime
    product_name: str | None
    image_url: str | None
    verdict: Literal["BUY", "CONSIDER", "SKIP"] | None
    selected_size: str | None
    total_cents: int | None
    currency: str | None


class SellerOut(BaseModel):
    name: str
    domain: str


class OptionOut(BaseModel):
    rank: int
    seller: SellerOut
    url: str
    total_cents: int
    summary: str
    price_check: PriceCheck
    fit_check: FitCheck
    seller_risk: SellerRisk


class ProductOut(BaseModel):
    name: str
    brand: str | None
    category: str | None
    attributes: dict[str, Any]
    image_url: str | None


class WhyNot(BaseModel):
    buy: str | None = None
    skip: str | None = None


class CheckResult(BaseModel):
    id: UUID
    status: RunStatus
    current_step: str | None
    input_url: str
    created_at: datetime
    completed_at: datetime | None
    error: str | None
    unit: Literal["in", "cm"]  # display unit for fit rows (values are in cm)
    product: ProductOut | None
    selected_size: str | None
    verdict: Literal["BUY", "CONSIDER", "SKIP"] | None
    headline: str | None
    explanation: str | None
    why_not: WhyNot | None
    options: list[OptionOut]
