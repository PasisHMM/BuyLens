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


async def test_required_measurements(client, auth):
    resp = await client.put("/v1/profile", json={"unit": "in", "waist": 26}, headers=auth)
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
