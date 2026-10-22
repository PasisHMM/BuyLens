import pytest

from app.repos.brands import _like_pattern
from app.units import Unit, from_cm, to_cm


async def test_brand_search_is_public(client):
    resp = await client.get("/v1/brands", params={"q": "lev"})
    assert resp.status_code == 200
    assert [b["slug"] for b in resp.json()] == ["levis"]


async def test_brand_search_limit_is_bounded(client):
    assert (await client.get("/v1/brands", params={"limit": 500})).status_code == 422


def test_like_pattern_escapes_wildcards():
    assert _like_pattern("50%_off") == "%50\\%\\_off%"


@pytest.mark.parametrize("inches", [24, 25.5, 26, 30, 30.5, 36, 44.5])
def test_inch_round_trip_is_stable(inches):
    assert from_cm(to_cm(inches, Unit.IN), Unit.IN) == inches


def test_cm_passthrough():
    assert to_cm(66.04, Unit.CM) == 66.0
    assert from_cm(66.0, Unit.CM) == 66.0
