"""Data passed between pipeline stages, and the JSON contracts of the three result cards."""

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Dimension = Literal["waist", "inseam", "hips"]
Basis = Literal["body", "garment"]  # brand "fit to body" chart vs. measured garment
StepId = Literal["product", "prices", "fit", "seller"]
STEPS: tuple[StepId, ...] = ("product", "prices", "fit", "seller")
# Singular nouns for copy: "a hip measurement", "Hip measurement unavailable".
DIMENSION_NOUN = {"waist": "waist", "inseam": "inseam", "hips": "hip"}


# ── Extraction ───────────────────────────────────────────────────────────────
class Measure(BaseModel):
    cm: float
    basis: Basis


class SizeRow(BaseModel):
    label: str  # "26", "26x30", "M"
    measures: dict[str, Measure] = Field(default_factory=dict)


class SizeChart(BaseModel):
    rows: list[SizeRow]
    source: Literal["table", "llm", "shopify"]


class ProductExtract(BaseModel):
    """What one seller's page says about one product. Missing facts stay None, never guessed."""

    url: str
    canonical_url: str
    seller_domain: str
    name: str
    brand: str | None = None
    category: str | None = None
    gtin: str | None = None  # product-level GTIN only
    variant_gtins: list[str] = Field(default_factory=list)  # one per size/length
    mpn: str | None = None
    external_id: str | None = None
    color: str | None = None
    image_url: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)  # fabric, stretch, fit, wash
    price_cents: int = 0
    currency: str = "USD"
    shipping_cents: int | None = None
    in_stock: bool | None = None
    sizes: list[str] = Field(default_factory=list)
    size_chart: SizeChart | None = None
    review_rating: float | None = None
    review_count: int | None = None
    review_texts: list[str] = Field(default_factory=list)
    extracted_by: list[str] = Field(default_factory=list)

    def is_sufficient(self) -> bool:
        return bool(self.name) and self.price_cents > 0 and len(self.currency) == 3


# ── Sellers & candidates ─────────────────────────────────────────────────────
class ReturnPolicy(BaseModel):
    verified: bool = False
    window_days: int | None = None
    free: bool | None = None
    restocking_fee: bool | None = None
    title: str | None = None  # "30-day free returns"
    details: str | None = None


class ShippingPolicy(BaseModel):
    verified: bool = False
    free_over_cents: int | None = None
    flat_cents: int | None = None


class SellerInfo(BaseModel):
    id: UUID
    name: str
    domain: str
    official_brand_id: UUID | None
    adapter: str
    trust_rating: float | None
    return_policy: ReturnPolicy
    shipping_policy: ShippingPolicy


class Match(StrEnum):
    EXACT = "exact"  # same GTIN / MPN
    LIKELY = "likely"  # same brand, near-identical name


class Candidate(BaseModel):
    """One listing of the product at one allow-listed seller."""

    extract: ProductExtract
    seller: SellerInfo
    match: Match
    is_source: bool = False
    listing_id: UUID | None = None
    is_official: bool = False


# ── Card contracts (stored in check_options, returned by the API) ────────────
class PriceCheck(BaseModel):
    currency: str
    listing_cents: int
    shipping_cents: int | None  # None → "Shipping unknown"
    total_cents: int  # listing + known shipping (a lower bound when shipping is unknown)
    total_is_estimate: bool
    market_avg_cents: int | None  # excludes shipping; None with fewer than 3 comparables
    delta_cents: int | None  # negative = below market
    delta_pct: float | None
    comparable_count: int


class FitMatch(StrEnum):
    OK = "ok"
    TIGHT = "tight"
    LOOSE = "loose"
    SHORT = "short"
    LONG = "long"
    MISSING = "missing"


class FitRow(BaseModel):
    dimension: str
    user_cm: float
    garment_cm: float | None  # None → "—"
    basis: Basis | None
    match: FitMatch
    room_cm: float | None  # chart - you


class FitCheck(BaseModel):
    size_label: str  # "W26 / L30"
    rows: list[FitRow]
    confidence: Literal["high", "medium", "limited"]
    alerts: list[str]
    notes: str


class SellerRisk(BaseModel):
    seller_name: str
    is_official: bool
    trust_rating: float | None
    level: Literal["low", "medium", "high"]
    review_rating: float | None
    review_count: int | None
    return_policy: ReturnPolicy
    review_highlights: list[str]
    fit_signal: Literal["runs_small", "true_to_size", "runs_large", "unknown"] = "unknown"


class RankedOption(BaseModel):
    rank: int
    candidate: Candidate
    price: PriceCheck
    fit: FitCheck
    risk: SellerRisk
    score: float
    summary: str = ""


class Verdict(StrEnum):
    BUY = "BUY"
    CONSIDER = "CONSIDER"
    SKIP = "SKIP"


class Decision(BaseModel):
    verdict: Verdict
    reasons: list[str]  # reason codes, e.g. FIT_DATA_MISSING
    missing_dimensions: list[str] = Field(default_factory=list)


class Narrative(BaseModel):
    headline: str
    explanation: str
    why_not_buy: str | None
    why_not_skip: str | None
    option_summaries: list[str]
    written_by: Literal["llm", "template"]


# ── Run context ──────────────────────────────────────────────────────────────
class FitMemoryEntry(BaseModel):
    brand_id: UUID | None
    category: str
    dimension: str
    ease_adjust_cm: float


class DecisionMemory(BaseModel):
    price_sensitivity: float = 0.5
    risk_aversion: float = 0.5
    fit_strictness: float = 0.5


class MemorySnapshot(BaseModel):
    fit: list[FitMemoryEntry] = Field(default_factory=list)
    decision: DecisionMemory = Field(default_factory=DecisionMemory)

    def ease_adjust(self, brand_id: UUID | None, category: str | None, dimension: str) -> float:
        """Brand-specific memory wins; cross-brand memory (brand_id = None) applies at half weight."""
        for entry in self.fit:
            if (
                entry.brand_id == brand_id
                and brand_id
                and entry.category == category
                and entry.dimension == dimension
            ):
                return entry.ease_adjust_cm
        for entry in self.fit:
            if entry.brand_id is None and entry.category == category and entry.dimension == dimension:
                return entry.ease_adjust_cm / 2
        return 0.0


class ProfileSnapshot(BaseModel):
    unit: Literal["in", "cm"]
    measurements_cm: dict[str, float]
    brand_ids: list[UUID] = Field(default_factory=list)


class SizeChoice(BaseModel):
    label: str
    display: str  # "W26 / L30"
    row: SizeRow | None
