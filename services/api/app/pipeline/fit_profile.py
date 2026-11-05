"""Fit profile rules: Quick Fit sizes and Personal Fit measurements live side by side.

The mode is only a setting, so switching never deletes the other mode's data (docs/redesign-plan.md §2.2).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.pipeline.models import Basis, Dimension, FitCategory, FitMode, QuickSize, SizeSystem


class InvalidProfile(ValueError):
    pass


@dataclass(frozen=True)
class Measurement:
    value_cm: float
    basis: Basis = Basis.BODY
    note: str | None = None


@dataclass(frozen=True)
class FitProfile:
    mode: FitMode
    size_system: SizeSystem | None = None
    quick_sizes: Mapping[FitCategory, QuickSize] = field(default_factory=dict)
    measurements: Mapping[Dimension, Measurement] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileUpdate:
    """A section left as None keeps what is stored; a provided section replaces it."""

    mode: FitMode
    size_system: SizeSystem | None = None
    quick_sizes: Mapping[FitCategory, QuickSize] | None = None
    measurements: Mapping[Dimension, Measurement] | None = None


def merge_profile(stored: FitProfile | None, update: ProfileUpdate) -> FitProfile:
    """The profile after an update, or InvalidProfile if the chosen mode would have nothing to use."""
    base = stored or FitProfile(update.mode)
    merged = FitProfile(
        mode=update.mode,
        size_system=update.size_system or base.size_system,
        quick_sizes=base.quick_sizes if update.quick_sizes is None else update.quick_sizes,
        measurements=base.measurements if update.measurements is None else update.measurements,
    )
    if merged.mode is FitMode.QUICK_FIT and not merged.quick_sizes:
        raise InvalidProfile("Pick a size for at least one category.")
    if merged.mode is FitMode.PERSONAL_FIT and not merged.measurements:
        raise InvalidProfile("Add at least one measurement.")
    return merged


def quick_size_for(profile: FitProfile, category: FitCategory) -> QuickSize | None:
    """The size saved for this category. Another category's size is never used in its place."""
    return profile.quick_sizes.get(category)


def body_measurements_cm(profile: FitProfile) -> dict[str, float]:
    """What today's fit check may compare: Personal Fit body values only.

    Quick Fit stays approximate, so saved measurements don't leak into it. Garment values wait for
    chart-basis matching in Phase 3.
    """
    if profile.mode is not FitMode.PERSONAL_FIT:
        return {}
    return {d.value: m.value_cm for d, m in profile.measurements.items() if m.basis is Basis.BODY}
