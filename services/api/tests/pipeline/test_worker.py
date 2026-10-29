"""Worker job behaviour: the shared seller allow-list under concurrent jobs."""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest

from app import worker
from app.pipeline.models import SellerInfo
from tests.fakes import seller


class SlowSellersStore:
    """Seller lookups wait until the test releases them, like a slow database."""

    def __init__(self, sellers: list[SellerInfo]) -> None:
        self.sellers_result = sellers
        self.release = asyncio.Event()

    async def sellers(self) -> list[SellerInfo]:
        await self.release.wait()
        return self.sellers_result


class Deps:
    def __init__(self, store: SlowSellersStore) -> None:
        self.store = store


@pytest.fixture(autouse=True)
def no_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run_check(deps: Any, run_id: UUID) -> None:
        pass

    monkeypatch.setattr(worker, "run_check", run_check)


def job_ctx(store: SlowSellersStore, domains: set[str]) -> dict[str, Any]:
    allowed = set(domains)
    return {"allowed": allowed, "host_allowed": worker.host_checker(allowed), "deps": Deps(store)}


async def test_allowed_store_stays_allowed_while_another_job_refreshes_the_list() -> None:
    store = SlowSellersStore([seller("shop.test")])
    ctx = job_ctx(store, {"shop.test"})

    job = asyncio.create_task(worker.run_check_job(ctx, str(uuid4())))
    await asyncio.sleep(0)  # the job is now waiting on the seller lookup

    # A check already running in parallel fetches from shop.test at this moment.
    assert ctx["host_allowed"]("www.shop.test")

    store.release.set()
    await job


async def test_refresh_applies_enabled_and_disabled_sellers() -> None:
    store = SlowSellersStore([seller("new.test")])
    store.release.set()
    ctx = job_ctx(store, {"old.test"})

    await worker.run_check_job(ctx, str(uuid4()))

    assert ctx["host_allowed"]("new.test")
    assert not ctx["host_allowed"]("old.test")
