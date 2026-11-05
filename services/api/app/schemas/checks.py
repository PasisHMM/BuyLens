from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.pipeline.models import FitCheck, FitMode, FitOutcome, PriceCheck, SellerRisk

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
    fit_outcome: FitOutcome | None
    selected_size: str | None
    total_cents: int | None
    currency: str | None


class SellerOut(BaseModel):
    name: str
    domain: str


class OptionOut(BaseModel):
    rank: int
    listing_id: UUID  # the stable offer identifier; seller.domain identifies the retailer
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


class HiddenMismatches(BaseModel):
    """Options left out of the visible results because a critical measurement doesn't fit."""

    count: int = 0
    reasons: list[str] = Field(default_factory=list)


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
    fit_mode_used: FitMode | None
    matches: list[OptionOut]
    uncertain: list[OptionOut]
    hidden_mismatches: HiddenMismatches
