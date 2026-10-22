import pytest

from tests.conftest import SUPABASE_URL, bearer


async def test_health_is_public(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_missing_token_is_rejected(client):
    resp = await client.get("/v1/profile")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret": "a-different-secret-that-is-also-long-enough"},
        {"aud": "anon"},
        {"iss": "https://evil.example.com/auth/v1"},
        {"exp_in": -60},
        {"sub": "not-a-uuid"},
    ],
    ids=["bad-signature", "wrong-audience", "wrong-issuer", "expired", "non-uuid-sub"],
)
async def test_invalid_tokens_are_rejected(client, make_token, overrides):
    resp = await client.get("/v1/profile", headers=bearer(make_token(**overrides)))
    assert resp.status_code == 401


async def test_unsigned_token_is_rejected(client):
    import jwt

    token = jwt.encode({"sub": "x", "aud": "authenticated", "iss": f"{SUPABASE_URL}/auth/v1"}, None, "none")
    resp = await client.get("/v1/profile", headers=bearer(token))
    assert resp.status_code == 401


async def test_anonymous_user_is_accepted(client, make_token):
    resp = await client.get("/v1/profile", headers=bearer(make_token(is_anonymous=True)))
    assert resp.status_code == 404  # authenticated, just no profile yet
