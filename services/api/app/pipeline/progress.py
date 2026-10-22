"""Per-check progress events for the loading modal ("Step 3 of 4 · Comparing your measurements").

Backed by a Redis Stream per run: events are replayable (a page that connects late, or
reconnects with Last-Event-ID, still sees every step) and expire an hour after the run.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import Redis

from app.pipeline.models import STEPS, StepId

EVENT_TTL_S = 3600
CANCEL_TTL_S = 600
TERMINAL = ("complete", "failed", "cancelled")

STEP_LABELS: dict[StepId, str] = {
    "product": "Finding product details",
    "prices": "Comparing prices",
    "fit": "Comparing your measurements",
    "seller": "Reviewing seller risk",
}


class ProgressEvent(BaseModel):
    type: Literal["step", "complete", "failed", "cancelled"]
    step: StepId | None = None
    status: Literal["active", "done"] | None = None
    index: int | None = None  # 1-based, for "Step 3 of 4"
    total: int = len(STEPS)
    label: str | None = None
    detail: str | None = None
    message: str | None = None  # user-safe text for failed/cancelled


class EventBus(Protocol):
    async def publish(self, run_id: UUID, event: ProgressEvent) -> str: ...
    async def read(self, run_id: UUID, after: str, block_ms: int) -> list[tuple[str, ProgressEvent]]: ...
    async def request_cancel(self, run_id: UUID) -> None: ...
    async def is_cancelled(self, run_id: UUID) -> bool: ...


class RedisEventBus:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(run_id: UUID) -> str:
        return f"buylens:check:{run_id}:events"

    async def publish(self, run_id: UUID, event: ProgressEvent) -> str:
        key = self._key(run_id)
        event_id = await self._redis.xadd(key, {"e": event.model_dump_json()}, maxlen=100)
        await self._redis.expire(key, EVENT_TTL_S)
        return event_id.decode() if isinstance(event_id, bytes) else str(event_id)

    async def read(self, run_id: UUID, after: str, block_ms: int) -> list[tuple[str, ProgressEvent]]:
        result = await self._redis.xread({self._key(run_id): after}, block=block_ms, count=50)
        events = []
        for _stream, entries in result or []:
            for event_id, fields in entries:
                raw = fields.get(b"e") or fields.get("e")
                eid = event_id.decode() if isinstance(event_id, bytes) else str(event_id)
                events.append((eid, ProgressEvent.model_validate_json(raw)))
        return events

    async def request_cancel(self, run_id: UUID) -> None:
        await self._redis.set(f"buylens:check:{run_id}:cancel", "1", ex=CANCEL_TTL_S)

    async def is_cancelled(self, run_id: UUID) -> bool:
        return bool(await self._redis.exists(f"buylens:check:{run_id}:cancel"))


class MemoryEventBus:
    """In-process bus for tests and local runs without Redis."""

    def __init__(self) -> None:
        self._events: dict[UUID, list[tuple[str, ProgressEvent]]] = {}
        self._cancelled: set[UUID] = set()
        self._cond = asyncio.Condition()

    async def publish(self, run_id: UUID, event: ProgressEvent) -> str:
        async with self._cond:
            events = self._events.setdefault(run_id, [])
            event_id = f"{len(events) + 1}-0"
            events.append((event_id, event))
            self._cond.notify_all()
        return event_id

    async def read(self, run_id: UUID, after: str, block_ms: int) -> list[tuple[str, ProgressEvent]]:
        def pending() -> list[tuple[str, ProgressEvent]]:
            seq = int(after.split("-")[0]) if after not in ("0", "$") else 0
            return [(i, e) for i, e in self._events.get(run_id, []) if int(i.split("-")[0]) > seq]

        async with self._cond:
            if not pending():
                try:
                    await asyncio.wait_for(self._cond.wait_for(lambda: bool(pending())), block_ms / 1000)
                except TimeoutError:
                    return []
            return pending()

    async def request_cancel(self, run_id: UUID) -> None:
        self._cancelled.add(run_id)

    async def is_cancelled(self, run_id: UUID) -> bool:
        return run_id in self._cancelled


class CancelledByUser(Exception):
    pass


class StepHandle:
    def __init__(self) -> None:
        self.detail: str | None = None


class Progress:
    def __init__(self, bus: EventBus, run_id: UUID, on_step: "StepCallback | None" = None) -> None:
        self._bus = bus
        self._run_id = run_id
        self._on_step = on_step

    @asynccontextmanager
    async def step(self, step: StepId) -> AsyncIterator[StepHandle]:
        if await self._bus.is_cancelled(self._run_id):
            raise CancelledByUser
        index = STEPS.index(step) + 1
        label = STEP_LABELS[step]
        if self._on_step:
            await self._on_step(step)
        await self._bus.publish(
            self._run_id, ProgressEvent(type="step", step=step, status="active", index=index, label=label)
        )
        handle = StepHandle()
        yield handle
        await self._bus.publish(
            self._run_id,
            ProgressEvent(
                type="step", step=step, status="done", index=index, label=label, detail=handle.detail
            ),
        )

    async def finish(
        self, kind: Literal["complete", "failed", "cancelled"], message: str | None = None
    ) -> None:
        await self._bus.publish(self._run_id, ProgressEvent(type=kind, message=message))


class StepCallback(Protocol):
    async def __call__(self, step: StepId) -> None: ...
