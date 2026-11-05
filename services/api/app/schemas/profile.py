from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.pipeline.fit_profile import Measurement, ProfileUpdate
from app.pipeline.measurements import DIMENSIONS as CATALOG
from app.pipeline.measurements import is_plausible
from app.pipeline.models import Basis, Dimension, FitCategory, FitMode, QuickSize, SizeSystem
from app.units import Unit, to_cm

MAX_BRANDS = 30
_OLD_FIELDS = {"waist", "inseam", "hips"}
_NEW_FIELDS = {"fit_mode", "size_system", "quick_sizes", "measurements"}


class Brand(BaseModel):
    id: UUID
    name: str
    slug: str


class MeasurementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: Dimension
    value: float = Field(gt=0)
    basis: Basis = Basis.BODY
    note: str | None = Field(default=None, max_length=200)


def _plausible_cm(dimension: Dimension, value: float, unit: Unit) -> float:
    # Values outside the catalog's plausible ranges are almost always a unit mix-up
    # (e.g. "66" typed while the toggle is on IN), so the error message points at the toggle.
    cm = to_cm(value, unit)
    if not is_plausible(dimension, cm):
        name = CATALOG[dimension].label.split(" /")[0]
        raise ValueError(f"{name} looks off. Check the unit (IN / cm).")
    return cm


class ProfileIn(BaseModel):
    """Body of PUT /v1/profile, in the unit the user chose on the IN / cm toggle.

    Two shapes are accepted. The current one names a `fit_mode` plus the sections to replace; a section
    left out keeps what is stored. The older `{unit, waist, inseam, hips}` still means Personal Fit
    with body measurements, for clients that haven't updated.
    """

    model_config = ConfigDict(extra="forbid")

    unit: Unit | None = None
    fit_mode: FitMode | None = None
    size_system: SizeSystem | None = None
    quick_sizes: dict[FitCategory, QuickSize] | None = None
    measurements: list[MeasurementIn] | None = None
    waist: float | None = Field(default=None, gt=0)
    inseam: float | None = Field(default=None, gt=0)
    hips: float | None = Field(default=None, gt=0)
    brand_ids: list[UUID] | None = Field(default=None, max_length=MAX_BRANDS)

    @field_validator("brand_ids")
    @classmethod
    def dedupe(cls, ids: list[UUID] | None) -> list[UUID] | None:
        return None if ids is None else list(dict.fromkeys(ids))

    @model_validator(mode="after")
    def consistent(self) -> "ProfileIn":
        is_old = bool(self.model_fields_set & _OLD_FIELDS)
        if is_old and self.model_fields_set & _NEW_FIELDS:
            raise ValueError("Send either waist/inseam/hips or fit_mode, not both.")
        if is_old:
            self._check_old_body()
        else:
            self._check_new_body()
        self.to_update()  # parses every value, so bad input is rejected here, where it enters
        return self

    def _check_old_body(self) -> None:
        if self.unit is None or self.waist is None or self.inseam is None:
            raise ValueError("unit, waist and inseam are required.")

    def _check_new_body(self) -> None:
        if self.fit_mode is None:
            raise ValueError("fit_mode is required.")
        if self.measurements is None:
            return
        if self.unit is None:
            raise ValueError("A unit is required with measurements.")
        dimensions = [m.dimension for m in self.measurements]
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("Each measurement can be sent only once.")

    def _old_measurements(self, unit: Unit) -> dict[Dimension, Measurement]:
        values = {Dimension.WAIST: self.waist, Dimension.INSEAM: self.inseam, Dimension.HIPS: self.hips}
        return {d: Measurement(_plausible_cm(d, v, unit)) for d, v in values.items() if v is not None}

    def to_update(self) -> ProfileUpdate:
        unit = self.unit or Unit.CM  # measurements always arrive with a unit: see `consistent`
        if self.fit_mode is None:  # only the older body has no mode
            return ProfileUpdate(FitMode.PERSONAL_FIT, measurements=self._old_measurements(unit))
        measurements = None
        if self.measurements is not None:
            measurements = {
                m.dimension: Measurement(_plausible_cm(m.dimension, m.value, unit), m.basis, m.note)
                for m in self.measurements
            }
        return ProfileUpdate(self.fit_mode, self.size_system, self.quick_sizes, measurements)

    def brands_to_save(self) -> list[UUID] | None:
        """None keeps saved brands. The older body always replaced them, so it still does."""
        return self.brand_ids or [] if self.fit_mode is None else self.brand_ids


class MeasurementOut(BaseModel):
    dimension: Dimension
    value: float
    basis: Basis
    note: str | None


class ProfileOut(BaseModel):
    """Measurements are returned in the user's chosen unit, ready for display."""

    unit: Unit
    fit_mode: FitMode
    size_system: SizeSystem | None
    quick_sizes: dict[FitCategory, QuickSize]
    measurements: list[MeasurementOut]
    # Older clients read these three; `measurements` is the full list.
    waist: float | None
    inseam: float | None
    hips: float | None
    brands: list[Brand]
    updated_at: datetime
