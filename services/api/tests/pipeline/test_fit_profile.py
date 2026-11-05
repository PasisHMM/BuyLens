"""Quick Fit and Personal Fit live side by side; switching mode never loses data (redesign plan §2.2)."""

import pytest

from app.pipeline.fit_profile import (
    FitProfile,
    InvalidProfile,
    Measurement,
    ProfileUpdate,
    body_measurements_cm,
    merge_profile,
    quick_size_for,
)
from app.pipeline.models import Basis, Dimension, FitCategory, FitMode, QuickSize, SizeSystem

TOPS, BOTTOMS = FitCategory.TOPS, FitCategory.BOTTOMS
WAIST = {Dimension.WAIST: Measurement(66.0)}


def test_quick_fit_with_only_a_bottoms_size_is_valid() -> None:
    profile = merge_profile(None, ProfileUpdate(FitMode.QUICK_FIT, quick_sizes={BOTTOMS: QuickSize.M}))
    assert profile.mode is FitMode.QUICK_FIT
    assert profile.quick_sizes == {BOTTOMS: QuickSize.M}


def test_quick_fit_without_any_size_is_rejected() -> None:
    with pytest.raises(InvalidProfile, match="size"):
        merge_profile(None, ProfileUpdate(FitMode.QUICK_FIT))


def test_personal_fit_without_any_measurement_is_rejected() -> None:
    with pytest.raises(InvalidProfile, match="measurement"):
        merge_profile(None, ProfileUpdate(FitMode.PERSONAL_FIT))


def test_tops_and_bottoms_sizes_are_never_assumed_equal() -> None:
    profile = merge_profile(None, ProfileUpdate(FitMode.QUICK_FIT, quick_sizes={TOPS: QuickSize.S}))
    assert quick_size_for(profile, TOPS) is QuickSize.S
    assert quick_size_for(profile, BOTTOMS) is None


def test_separate_sizes_stay_separate() -> None:
    sizes = {TOPS: QuickSize.S, BOTTOMS: QuickSize.M}
    profile = merge_profile(None, ProfileUpdate(FitMode.QUICK_FIT, quick_sizes=sizes))
    assert quick_size_for(profile, TOPS) is QuickSize.S
    assert quick_size_for(profile, BOTTOMS) is QuickSize.M


def test_switching_to_personal_fit_keeps_quick_sizes() -> None:
    quick = merge_profile(None, ProfileUpdate(FitMode.QUICK_FIT, quick_sizes={TOPS: QuickSize.S}))
    personal = merge_profile(quick, ProfileUpdate(FitMode.PERSONAL_FIT, measurements=WAIST))
    assert personal.mode is FitMode.PERSONAL_FIT
    assert personal.quick_sizes == {TOPS: QuickSize.S}
    assert personal.measurements == WAIST


def test_switching_back_to_quick_fit_keeps_measurements() -> None:
    both = FitProfile(FitMode.PERSONAL_FIT, None, {TOPS: QuickSize.S}, WAIST)
    assert merge_profile(both, ProfileUpdate(FitMode.QUICK_FIT)).measurements == WAIST


def test_a_mode_switch_alone_is_valid_when_the_data_exists() -> None:
    both = FitProfile(FitMode.QUICK_FIT, None, {TOPS: QuickSize.S}, WAIST)
    assert merge_profile(both, ProfileUpdate(FitMode.PERSONAL_FIT)).mode is FitMode.PERSONAL_FIT


def test_an_update_replaces_only_the_sections_it_provides() -> None:
    stored = FitProfile(FitMode.QUICK_FIT, SizeSystem.EU, {TOPS: QuickSize.S}, WAIST)
    merged = merge_profile(stored, ProfileUpdate(FitMode.QUICK_FIT, quick_sizes={BOTTOMS: QuickSize.L}))
    assert merged.quick_sizes == {BOTTOMS: QuickSize.L}
    assert merged.measurements == WAIST
    assert merged.size_system is SizeSystem.EU


def test_size_system_is_updated_when_provided() -> None:
    stored = FitProfile(FitMode.QUICK_FIT, SizeSystem.EU, {TOPS: QuickSize.S}, {})
    merged = merge_profile(stored, ProfileUpdate(FitMode.QUICK_FIT, size_system=SizeSystem.US))
    assert merged.size_system is SizeSystem.US


def test_clearing_every_measurement_is_rejected_in_personal_fit() -> None:
    stored = FitProfile(FitMode.PERSONAL_FIT, None, {}, WAIST)
    with pytest.raises(InvalidProfile, match="measurement"):
        merge_profile(stored, ProfileUpdate(FitMode.PERSONAL_FIT, measurements={}))


def test_only_body_measurements_reach_todays_fit_check() -> None:
    profile = FitProfile(
        FitMode.PERSONAL_FIT,
        None,
        {},
        {
            Dimension.WAIST: Measurement(66.0),
            Dimension.HIPS: Measurement(98.0, Basis.GARMENT, "My blue jeans"),
        },
    )
    assert body_measurements_cm(profile) == {"waist": 66.0}


def test_quick_fit_never_passes_saved_measurements_to_a_check() -> None:
    profile = FitProfile(FitMode.QUICK_FIT, None, {TOPS: QuickSize.S}, WAIST)
    assert body_measurements_cm(profile) == {}
