from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.pipeline.models import MemorySnapshot, ProfileSnapshot
from app.pipeline.progress import MemoryEventBus, ProgressEvent
from app.queue import MemoryRateLimiter
from app.routers.checks import get_check_repo
from app.schemas.checks import CheckResult, CheckSummary
from tests.conftest import bearer

PRODUCT_URL = "https://www.levi.com/US/en_US/p/501-cropped?utm_source=ig"
DESIGN = {"unit": "in", "waist": 26, "inseam": 30, "hips": 36}


class InMemoryCheckRepo:
    def __init__(self) -> None:
        self.runs: dict[UUID, dict] = {}

    async def seller_domains(self) -> list[str]:
        return ["levi.com", "nordstrom.com"]

    async def memory_snapshot(self, user_id: UUID) -> MemorySnapshot:
        return MemorySnapshot()

    async def active_runs(self, user_id: UUID) -> int:
        return sum(
            1 for r in self.runs.values() if r["user_id"] == user_id and r["status"] in ("queued", "running")
        )

    async def create_run(
        self, user_id, *, input_url, profile: ProfileSnapshot, memory, pipeline_version
    ) -> UUID:
        run_id = uuid4()
        self.runs[run_id] = {
            "user_id": user_id,
            "input_url": input_url,
            "status": "queued",
            "profile": profile,
        }
        return run_id

    def _own(self, user_id, run_id):
        run = self.runs.get(run_id)
        return run if run and run["user_id"] == user_id else None  # mirrors RLS

    async def status(self, user_id, run_id) -> str | None:
        run = self._own(user_id, run_id)
        return run["status"] if run else None

    async def get(self, user_id, run_id) -> CheckResult | None:
        run = self._own(user_id, run_id)
        if run is None:
            return None
        return CheckResult(
            id=run_id, status=run["status"], current_step=None, input_url=run["input_url"],
            created_at=datetime.now(UTC), completed_at=None, error=None, unit="in", product=None,
            selected_size=None, verdict=None, headline=None, explanation=None, why_not=None, options=[],
        )  # fmt: skip

    async def recent(self, user_id, limit) -> list[CheckSummary]:
        return [
            CheckSummary(id=i, status=r["status"], created_at=datetime.now(UTC), product_name=None, image_url=None,
                         verdict=None, selected_size=None, total_cents=None, currency=None)
            for i, r in self.runs.items() if r["user_id"] == user_id
        ][:limit]  # fmt: skip

    async def cancel_queued(self, user_id, run_id) -> bool:
        run = self._own(user_id, run_id)
        if run and run["status"] == "queued":
            run["status"] = "cancelled"
            return True
        return False


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[UUID] = []

    async def enqueue(self, run_id: UUID) -> None:
        self.jobs.append(run_id)


@pytest.fixture
def checks(app):
    repo, queue, bus = InMemoryCheckRepo(), FakeQueue(), MemoryEventBus()
    app.dependency_overrides[get_check_repo] = lambda: repo
    app.state.bus, app.state.queue, app.state.rate_limiter = bus, queue, MemoryRateLimiter()
    return repo, queue, bus


@pytest.fixture
def user(make_token):
    user_id = uuid4()
    return user_id, bearer(make_token(user_id))


async def with_profile(client, auth):
    assert (await client.put("/v1/profile", json=DESIGN, headers=auth)).status_code == 204


async def test_create_check_snapshots_profile_and_enqueues(client, checks, user):
    repo, queue, _ = checks
    _, auth = user
    await with_profile(client, auth)

    resp = await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)
    assert resp.status_code == 202
    run_id = UUID(resp.json()["id"])
    assert queue.jobs == [run_id]
    run = repo.runs[run_id]
    assert run["input_url"] == "https://www.levi.com/US/en_US/p/501-cropped"  # tracking stripped
    assert run["profile"].measurements_cm == {"waist": 66.0, "inseam": 76.2, "hips": 91.4}


@pytest.mark.parametrize(
    ("url", "detail"),
    [("https://www.zara.com/p/1", "We don't support this store yet."),
     ("javascript:alert(1)", "That doesn't look like a product link."),
     ("ftp://levi.com/p", "Only web links (https://…) can be checked.")],
)  # fmt: skip
async def test_rejects_unsupported_links(client, checks, user, url, detail):
    _, auth = user
    await with_profile(client, auth)
    resp = await client.post("/v1/checks", json={"url": url}, headers=auth)
    assert (resp.status_code, resp.json()["detail"]) == (422, detail)


async def test_requires_measurements(client, checks, user):
    resp = await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=user[1])
    assert (resp.status_code, resp.json()["detail"]) == (409, "Save your measurements first.")


async def test_requires_auth(client, checks):
    assert (await client.post("/v1/checks", json={"url": PRODUCT_URL})).status_code == 401


async def test_limits_concurrent_and_rapid_checks(client, checks, user):
    repo, _, _ = checks
    _, auth = user
    await with_profile(client, auth)
    statuses = [
        (await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)).status_code
        for _ in range(3)
    ]
    assert statuses == [202, 202, 429]  # two may run at once

    for run in repo.runs.values():
        run["status"] = "done"
    statuses = [
        (await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)).status_code
        for _ in range(12)
    ]
    assert 429 in statuses  # 10 per 10 minutes


async def test_other_users_checks_are_invisible(client, checks, user, make_token):
    _, auth = user
    await with_profile(client, auth)
    run_id = (await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)).json()["id"]
    stranger = bearer(make_token(uuid4()))
    for method, path in [("GET", f"/v1/checks/{run_id}"), ("DELETE", f"/v1/checks/{run_id}"),
                         ("GET", f"/v1/checks/{run_id}/events")]:  # fmt: skip
        assert (await client.request(method, path, headers=stranger)).status_code == 404
    assert (await client.get(f"/v1/checks/{run_id}", headers=auth)).status_code == 200


async def test_cancel_queued_check(client, checks, user):
    repo, _, bus = checks
    _, auth = user
    await with_profile(client, auth)
    run_id = UUID((await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)).json()["id"])

    resp = await client.delete(f"/v1/checks/{run_id}", headers=auth)
    assert resp.status_code == 202
    assert repo.runs[run_id]["status"] == "cancelled"
    assert await bus.is_cancelled(run_id)
    assert (await client.delete(f"/v1/checks/{run_id}", headers=auth)).status_code == 409


async def test_event_stream_replays_and_ends(client, checks, user):
    _, _, bus = checks
    _, auth = user
    await with_profile(client, auth)
    run_id = UUID((await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)).json()["id"])
    await bus.publish(run_id, ProgressEvent(type="step", step="product", status="active", index=1))
    await bus.publish(
        run_id, ProgressEvent(type="step", step="product", status="done", index=1, detail="501")
    )
    await bus.publish(run_id, ProgressEvent(type="complete"))

    resp = await client.get(f"/v1/checks/{run_id}/events", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    blocks = [b for b in resp.text.split("\n\n") if b]
    assert [b.splitlines()[1] for b in blocks] == ["event: step", "event: step", "event: complete"]
    assert blocks[0].startswith("id: 1-0")
    assert '"detail":"501"' in blocks[1]

    # Reconnect with Last-Event-ID: only what came after.
    resp = await client.get(f"/v1/checks/{run_id}/events", headers={**auth, "Last-Event-ID": "2-0"})
    assert [b.splitlines()[1] for b in resp.text.split("\n\n") if b] == ["event: complete"]


async def test_event_stream_for_finished_run_without_events(client, checks, user, monkeypatch):
    repo, _, _ = checks
    _, auth = user
    await with_profile(client, auth)
    run_id = UUID((await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)).json()["id"])
    repo.runs[run_id]["status"] = "done"  # e.g. the Redis stream expired
    monkeypatch.setattr("app.routers.checks.KEEPALIVE_MS", 10)

    resp = await client.get(f"/v1/checks/{run_id}/events", headers=auth)
    assert "event: complete" in resp.text


async def test_recent_checks(client, checks, user):
    _, auth = user
    await with_profile(client, auth)
    await client.post("/v1/checks", json={"url": PRODUCT_URL}, headers=auth)
    resp = await client.get("/v1/checks", params={"limit": 5}, headers=auth)
    assert resp.status_code == 200 and len(resp.json()) == 1
