from uuid import uuid4

import pytest

from tests.conftest import EVERLANE, LEVIS, bearer

DESIGN_PROFILE = {
    "unit": "in",
    "waist": 26,
    "inseam": 30,
    "hips": 36,
    "brand_ids": [str(LEVIS.id), str(EVERLANE.id)],
}


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def auth(make_token, user_id):
    return bearer(make_token(user_id))


async def test_new_user_has_no_profile(client, auth):
    resp = await client.get("/v1/profile", headers=auth)
    assert resp.status_code == 404


async def test_save_and_read_design_profile(client, auth, profile_repo, user_id):
    resp = await client.put("/v1/profile", json=DESIGN_PROFILE, headers=auth)
    assert resp.status_code == 204

    # Stored canonically in centimeters.
    assert profile_repo.rows[user_id].measurements_cm == {"waist": 66.0, "inseam": 76.2, "hips": 91.4}

    resp = await client.get("/v1/profile", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["unit"], body["waist"], body["inseam"], body["hips"]) == ("in", 26.0, 30.0, 36.0)
    assert [b["slug"] for b in body["brands"]] == ["everlane", "levis"]


async def test_centimeter_profile(client, auth, profile_repo, user_id):
    resp = await client.put("/v1/profile", json={"unit": "cm", "waist": 66, "inseam": 76}, headers=auth)
    assert resp.status_code == 204
    body = (await client.get("/v1/profile", headers=auth)).json()
    assert (body["unit"], body["waist"], body["inseam"], body["hips"]) == ("cm", 66.0, 76.0, None)


async def test_clearing_optional_hips(client, auth, profile_repo, user_id):
    await client.put("/v1/profile", json=DESIGN_PROFILE, headers=auth)
    await client.put("/v1/profile", json={**DESIGN_PROFILE, "hips": None}, headers=auth)
    assert "hips" not in profile_repo.rows[user_id].measurements_cm


@pytest.mark.parametrize(
    "patch",
    [
        {"unit": "cm", "waist": 26},  # inches typed while the toggle is on cm
        {"unit": "in", "inseam": 76},  # cm typed while the toggle is on IN
        {"inseam": 0},
        {"waist": -5},
        {"unit": "mm"},
        {"height": 170},  # unknown field
    ],
    ids=["cm-too-small", "in-too-large", "zero", "negative", "bad-unit", "extra-field"],
)
async def test_rejects_implausible_or_malformed_input(client, auth, patch):
    resp = await client.put("/v1/profile", json={**DESIGN_PROFILE, **patch}, headers=auth)
    assert resp.status_code == 422


async def test_unit_mixup_message_points_at_toggle(client, auth):
    resp = await client.put("/v1/profile", json={**DESIGN_PROFILE, "unit": "cm"}, headers=auth)
    assert resp.status_code == 422
    assert "Check the unit (IN / cm)" in resp.text


@pytest.mark.parametrize(
    "body",
    [{"unit": "in", "waist": 26}, {"unit": "in", "inseam": 30}, {"waist": 26, "inseam": 30}],
    ids=["no-inseam", "no-waist", "no-unit"],
)
async def test_the_older_body_still_requires_unit_waist_and_inseam(client, auth, body):
    resp = await client.put("/v1/profile", json=body, headers=auth)
    assert resp.status_code == 422


async def test_unknown_brand(client, auth):
    resp = await client.put("/v1/profile", json={**DESIGN_PROFILE, "brand_ids": [str(uuid4())]}, headers=auth)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Unknown brand."


async def test_duplicate_brands_are_collapsed(client, auth, profile_repo, user_id):
    payload = {**DESIGN_PROFILE, "brand_ids": [str(LEVIS.id), str(LEVIS.id)]}
    assert (await client.put("/v1/profile", json=payload, headers=auth)).status_code == 204
    assert [b.slug for b in profile_repo.rows[user_id].brands] == ["levis"]


async def test_users_are_isolated(client, make_token):
    alice, bob = bearer(make_token(uuid4())), bearer(make_token(uuid4()))
    await client.put("/v1/profile", json=DESIGN_PROFILE, headers=alice)
    assert (await client.get("/v1/profile", headers=bob)).status_code == 404


QUICK = {"fit_mode": "quick_fit", "size_system": "eu", "quick_sizes": {"tops": "S", "bottoms": "M"}}
PERSONAL = {
    "fit_mode": "personal_fit",
    "unit": "cm",
    "measurements": [
        {"dimension": "chest", "value": 90},
        {"dimension": "waist", "value": 76, "basis": "garment", "note": "My blue jeans"},
    ],
}


async def test_quick_fit_round_trip_keeps_tops_and_bottoms_separate(client, auth):
    assert (await client.put("/v1/profile", json=QUICK, headers=auth)).status_code == 204
    body = (await client.get("/v1/profile", headers=auth)).json()
    assert body["fit_mode"] == "quick_fit"
    assert body["size_system"] == "eu"
    assert body["quick_sizes"] == {"tops": "S", "bottoms": "M"}
    assert body["measurements"] == []
    assert (body["waist"], body["inseam"], body["hips"]) == (None, None, None)


async def test_personal_fit_round_trip_with_basis_and_note(client, auth):
    assert (await client.put("/v1/profile", json=PERSONAL, headers=auth)).status_code == 204
    body = (await client.get("/v1/profile", headers=auth)).json()
    assert body["fit_mode"] == "personal_fit"
    assert body["measurements"] == [
        {"dimension": "chest", "value": 90.0, "basis": "body", "note": None},
        {"dimension": "waist", "value": 76.0, "basis": "garment", "note": "My blue jeans"},
    ]


async def test_old_body_means_personal_fit_with_body_measurements(client, auth):
    assert (await client.put("/v1/profile", json=DESIGN_PROFILE, headers=auth)).status_code == 204
    body = (await client.get("/v1/profile", headers=auth)).json()
    assert body["fit_mode"] == "personal_fit"
    assert {m["dimension"]: m["basis"] for m in body["measurements"]} == {
        "waist": "body",
        "inseam": "body",
        "hips": "body",
    }
    assert (body["waist"], body["inseam"], body["hips"]) == (26.0, 30.0, 36.0)  # older clients read these


async def test_switching_modes_loses_nothing(client, auth):
    await client.put("/v1/profile", json=QUICK, headers=auth)
    await client.put("/v1/profile", json=PERSONAL, headers=auth)
    resp = await client.put("/v1/profile", json={"fit_mode": "quick_fit"}, headers=auth)
    assert resp.status_code == 204
    body = (await client.get("/v1/profile", headers=auth)).json()
    assert body["fit_mode"] == "quick_fit"
    assert body["quick_sizes"] == {"tops": "S", "bottoms": "M"}
    assert [m["dimension"] for m in body["measurements"]] == ["chest", "waist"]


async def test_a_new_body_without_brands_keeps_saved_brands(client, auth):
    await client.put("/v1/profile", json=DESIGN_PROFILE, headers=auth)
    await client.put("/v1/profile", json=QUICK, headers=auth)
    body = (await client.get("/v1/profile", headers=auth)).json()
    assert [b["slug"] for b in body["brands"]] == ["everlane", "levis"]


async def test_old_body_without_brands_still_clears_them(client, auth):
    await client.put("/v1/profile", json=DESIGN_PROFILE, headers=auth)
    await client.put("/v1/profile", json={"unit": "in", "waist": 26, "inseam": 30}, headers=auth)
    assert (await client.get("/v1/profile", headers=auth)).json()["brands"] == []


async def test_first_quick_fit_profile_defaults_to_centimeters(client, auth):
    await client.put("/v1/profile", json=QUICK, headers=auth)
    assert (await client.get("/v1/profile", headers=auth)).json()["unit"] == "cm"


async def test_a_mode_switch_keeps_the_saved_unit(client, auth):
    await client.put("/v1/profile", json=DESIGN_PROFILE, headers=auth)
    await client.put("/v1/profile", json=QUICK, headers=auth)
    assert (await client.get("/v1/profile", headers=auth)).json()["unit"] == "in"


_CM_WAIST = {"dimension": "waist", "value": 66}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"fit_mode": "quick_fit"}, "Pick a size"),
        ({"fit_mode": "personal_fit"}, "at least one measurement"),
        ({"fit_mode": "quick_fit", "quick_sizes": {"shoes": "M"}}, ""),
        ({"fit_mode": "quick_fit", "quick_sizes": {"tops": "XXL"}}, ""),
        ({"fit_mode": "chest_only", "quick_sizes": {"tops": "S"}}, ""),
        (
            {"fit_mode": "personal_fit", "unit": "cm", "measurements": [{"dimension": "neck", "value": 38}]},
            "",
        ),
        ({"fit_mode": "personal_fit", "measurements": [_CM_WAIST]}, "unit"),
        ({"fit_mode": "personal_fit", "unit": "cm", "measurements": [_CM_WAIST, _CM_WAIST]}, "once"),
        (
            {"fit_mode": "personal_fit", "unit": "cm", "measurements": [{"dimension": "chest", "value": 20}]},
            "Chest looks off",
        ),
        ({"quick_sizes": {"tops": "S"}}, "fit_mode"),
        ({"unit": "cm"}, "fit_mode"),
        ({"fit_mode": "quick_fit", "quick_sizes": {"tops": "S"}, "waist": 66}, "not both"),
    ],
    ids=[
        "quick-no-size",
        "personal-no-measurement",
        "unknown-category",
        "unknown-size",
        "unknown-mode",
        "unknown-measurement",
        "measurements-without-unit",
        "duplicate-measurement",
        "implausible",
        "no-mode",
        "nothing-to-save",
        "old-and-new-mixed",
    ],
)
async def test_rejects_invalid_new_bodies(client, auth, payload, message):
    resp = await client.put("/v1/profile", json=payload, headers=auth)
    assert resp.status_code == 422
    assert message in resp.text
