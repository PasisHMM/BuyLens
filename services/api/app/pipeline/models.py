"""Data passed between pipeline stages, and the JSON contracts of the three result cards."""

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Measurement model (docs/glossary.md) ─────────────────────────────────────
# Values are stored as-is in Postgres enums and lookup tables; an integration test keeps them equal.
class Dimension(StrEnum):
    """A body measurement. Chest and bust are one measurement: the fullest girth of the upper body."""

    CHEST = "chest"
    WAIST = "waist"
    HIPS = "hips"
    SHOULDERS = "shoulders"
    INSEAM = "inseam"
    SLEEVE = "sleeve"
    HEIGHT = "height"


class Basis(StrEnum):
    """What a number measures: a person's body, or a garment laid flat."""

    BODY = "body"
    GARMENT = "garment"


class FitMode(StrEnum):
    """How a profile describes the user. Quick Fit sizes are approximate; Personal Fit values are exact."""

    QUICK_FIT = "quick_fit"
    PERSONAL_FIT = "personal_fit"


class FitOutcome(StrEnum):
    """Result of comparing a profile with one listing's size data."""

    MATCH = "match"  # one size clearly fits, with nothing known against it
    UNCERTAIN = "uncertain"  # between sizes, an additional concern, or not enough evidence
    MISMATCH = "mismatch"  # a critical measurement is verified outside the permitted range


class FitCategory(StrEnum):
    """Garment groups that have agreed fit rules."""

    BOTTOMS = "bottoms"  # jeans and pants
    TOPS = "tops"
    DRESSES = "dresses"
    OUTERWEAR = "outerwear"


class SizeSystem(StrEnum):
    EU = "eu"
    US = "us"


class QuickSize(StrEnum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


StepId = Literal["product", "prices", "fit", "seller"]
STEPS: tuple[StepId, ...] = ("product", "prices", "fit", "seller")


# ── Extraction ───────────────────────────────────────────────────────────────
class Measure(BaseModel):
    cm: float  # the published value, or the middle of a published range
    basis: Basis
    min_cm: float | None = None  # the published range, when the chart gives one
    max_cm: float | None = None


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


class DimensionStatus(StrEnum):
    INSIDE = "inside"  # within the published range
    NEAR = "near"  # outside the range, within the approved tolerance
    OUTSIDE = "outside"  # beyond the tolerance
    MISSING = "missing"  # no comparable value: never counts against a product


class FitRow(BaseModel):
    dimension: str
    role: Literal["critical", "secondary"] = "critical"
    user_cm: float | None = None  # None in Quick Fit: a size label says nothing exact about a person
    chart_min_cm: float | None = None
    chart_max_cm: float | None = None
    basis: Basis | None = None
    status: DimensionStatus = DimensionStatus.MISSING


class FitCheck(BaseModel):
    # Defaults let results stored before this contract load as "not enough evidence".
    mode: FitMode = FitMode.PERSONAL_FIT
    outcome: FitOutcome = FitOutcome.UNCERTAIN
    approximate: bool = False
    size_label: str | None = None  # "W26 / L30"; "S / M" when between sizes
    rows: list[FitRow] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class SellerRisk(BaseModel):
    seller_name: str
    is_official: bool
    trust_rating: float | None
    level: Literal["low", "medium", "high"] | None  # None: not enough data to say
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
    summary: str = ""


# ── Run context ──────────────────────────────────────────────────────────────
class FitMemoryEntry(BaseModel):
    brand_id: UUID | None
    category: str
    dimension: str
    ease_adjust_cm: float


class MemorySnapshot(BaseModel):
    fit: list[FitMemoryEntry] = Field(default_factory=list)

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
    measurements_cm: dict[str, float]  # body measurements
    brand_ids: list[UUID] = Field(default_factory=list)
    garment_cm: dict[str, float] = Field(default_factory=dict)  # measured from a garment that fits
    # Defaults keep runs queued before Quick Fit existed valid.
    fit_mode: FitMode = FitMode.PERSONAL_FIT
    quick_sizes: dict[FitCategory, QuickSize] = Field(default_factory=dict)
