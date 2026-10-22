import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.repos.profiles import StoredProfile, UnknownBrandError
from app.routers.brands import get_brand_repo
from app.routers.profile import get_profile_repo
from app.schemas.profile import Brand
from app.units import Unit

JWT_SECRET = "test-secret-with-at-least-32-bytes-of-entropy!!"
SUPABASE_URL = "https://test-project.supabase.co"

LEVIS = Brand(id=UUID("00000000-0000-0000-0000-00000000000a"), name="Levi's", slug="levis")
EVERLANE = Brand(id=UUID("00000000-0000-0000-0000-00000000000b"), name="Everlane", slug="everlane")
MADEWELL = Brand(id=UUID("00000000-0000-0000-0000-00000000000c"), name="Madewell", slug="madewell")
CATALOG = [EVERLANE, LEVIS, MADEWELL]


class InMemoryProfileRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, StoredProfile] = {}

    async def get(self, user_id: UUID) -> StoredProfile | None:
        return self.rows.get(user_id)

    async def save(
        self, user_id: UUID, *, unit: Unit, measurements_cm: dict[str, float], brand_ids: list[UUID]
    ) -> None:
        by_id = {b.id: b for b in CATALOG}
        if any(b not in by_id for b in brand_ids):
            raise UnknownBrandError
        self.rows[user_id] = StoredProfile(
            unit=unit,
            measurements_cm=dict(measurements_cm),
            brands=sorted((by_id[b] for b in brand_ids), key=lambda b: b.name),
            updated_at=datetime.now(UTC),
        )


class InMemoryBrandRepo:
    async def search(self, query: str | None, limit: int) -> list[Brand]:
        hits = [b for b in CATALOG if query is None or query.lower() in b.name.lower()]
        return hits[:limit]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        supabase_url=SUPABASE_URL,
        supabase_jwt_secret=SecretStr(JWT_SECRET),
        database_url="postgresql://unused/unused",
    )


@pytest.fixture
def profile_repo() -> InMemoryProfileRepo:
    return InMemoryProfileRepo()


@pytest.fixture
def app(settings: Settings, profile_repo: InMemoryProfileRepo) -> FastAPI:
    app = create_app(settings)
    app.dependency_overrides[get_profile_repo] = lambda: profile_repo
    app.dependency_overrides[get_brand_repo] = InMemoryBrandRepo
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # ASGITransport does not run the lifespan, so no database connection is attempted.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


TokenFactory = Callable[..., str]


@pytest.fixture
def make_token() -> TokenFactory:
    def factory(
        sub: UUID | str | None = None,
        *,
        secret: str = JWT_SECRET,
        aud: str = "authenticated",
        iss: str = f"{SUPABASE_URL}/auth/v1",
        exp_in: int = 3600,
        is_anonymous: bool = True,
    ) -> str:
        now = int(time.time())
        claims = {
            "sub": str(sub or uuid4()),
            "aud": aud,
            "iss": iss,
            "iat": now,
            "exp": now + exp_in,
            "role": "authenticated",
            "is_anonymous": is_anonymous,
        }
        return jwt.encode(claims, secret, algorithm="HS256")

    return factory


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
