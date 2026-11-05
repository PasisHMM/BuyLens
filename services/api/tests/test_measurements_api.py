"""GET /v1/measurements: the only catalog source for the web app (redesign plan §9, U5)."""

from app.pipeline.measurements import CATEGORY_RULES, DIMENSIONS
from app.pipeline.models import Dimension, FitCategory, QuickSize, SizeSystem


async def test_needs_no_sign_in_and_lists_every_measurement_and_category(client):
    resp = await client.get("/v1/measurements")
    assert resp.status_code == 200
    body = resp.json()
    assert [d["id"] for d in body["dimensions"]] == [d.value for d in DIMENSIONS]
    assert [c["id"] for c in body["categories"]] == [c.value for c in CATEGORY_RULES]
    assert body["quick_sizes"] == [s.value for s in QuickSize]
    assert body["size_systems"] == [s.value for s in SizeSystem]


async def test_ranges_and_labels_come_from_the_catalog(client):
    body = (await client.get("/v1/measurements")).json()
    waist = next(d for d in body["dimensions"] if d["id"] == "waist")
    assert waist["label"] == DIMENSIONS[Dimension.WAIST].label
    assert [waist["min_cm"], waist["max_cm"]] == list(DIMENSIONS[Dimension.WAIST].plausible_cm)


async def test_tops_are_chest_and_shoulders_with_waist_secondary(client):
    body = (await client.get("/v1/measurements")).json()
    tops = next(c for c in body["categories"] if c["id"] == FitCategory.TOPS)
    assert tops["label"] == "Tops"
    assert set(tops["critical"]) == {"chest", "shoulders"}
    assert tops["secondary"] == ["waist", "sleeve"]


async def test_lists_product_types_with_their_fit_category(client):
    body = (await client.get("/v1/measurements")).json()
    types = {t["id"]: t["fit_category"] for t in body["product_types"]}
    assert types["jeans"] == "bottoms"
    assert types["hoodies"] == "tops"
    assert types["skirts"] is None
    assert len(types) == 8
