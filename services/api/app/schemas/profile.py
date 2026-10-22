from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.units import Unit, to_cm

REQUIRED_DIMENSIONS = ("waist", "inseam")
OPTIONAL_DIMENSIONS = ("hips",)
DIMENSIONS = REQUIRED_DIMENSIONS + OPTIONAL_DIMENSIONS

# Plausible adult ranges in cm. Values outside these are almost always a unit mix-up
# (e.g. "66" typed while the toggle is on IN), so the error message points at the toggle.
PLAUSIBLE_CM: dict[str, tuple[float, float]] = {
    "waist": (45.0, 200.0),
    "inseam": (40.0, 120.0),
    "hips": (60.0, 200.0),
}

MAX_BRANDS = 30


class Brand(BaseModel):
    id: UUID
    name: str
    slug: str


class ProfileIn(BaseModel):
    """Body of PUT /v1/profile, in the unit the user chose on the IN / cm toggle."""

    model_config = ConfigDict(extra="forbid")

    unit: Unit
    waist: float = Field(gt=0)
    inseam: float = Field(gt=0)
    hips: float | None = Field(default=None, gt=0)
    brand_ids: list[UUID] = Field(default_factory=list, max_length=MAX_BRANDS)

    @field_validator("brand_ids")
    @classmethod
    def dedupe(cls, ids: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(ids))

    @model_validator(mode="after")
    def plausible(self) -> "ProfileIn":
        for dim, value_cm in self.measurements_cm().items():
            low, high = PLAUSIBLE_CM[dim]
            if not low <= value_cm <= high:
                raise ValueError(f"{dim.capitalize()} looks off. Check the unit (IN / cm).")
        return self

    def measurements_cm(self) -> dict[str, float]:
        values = {"waist": self.waist, "inseam": self.inseam, "hips": self.hips}
        return {dim: to_cm(v, self.unit) for dim, v in values.items() if v is not None}


class ProfileOut(BaseModel):
    """Measurements are returned in the user's chosen unit, ready for display."""

    unit: Unit
    waist: float | None
    inseam: float | None
    hips: float | None
    brands: list[Brand]
    updated_at: datetime
