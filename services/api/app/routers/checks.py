from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.auth import CurrentUser, current_user
from app.config import Settings
from app.db import Database, get_db
from app.pipeline.models import ProfileSnapshot
from app.pipeline.progress import TERMINAL, EventBus, ProgressEvent
from app.pipeline.urls import InvalidProductUrl, normalize_url, seller_domain_for
from app.queue import CheckQueue, RateLimiter
from app.repos.checks import CheckRepo, PgCheckRepo
from app.repos.profiles import ProfileRepo
from app.routers.profile import get_profile_repo
from app.schemas.checks import CheckCreated, CheckIn, CheckResult, CheckSummary

router = APIRouter(prefix="/v1/checks", tags=["checks"])

CHECKS_PER_WINDOW = 10
WINDOW_S = 600
MAX_ACTIVE_RUNS = 2
KEEPALIVE_MS = 15_000
DB_TO_EVENT = {"done": "complete", "failed": "failed", "cancelled": "cancelled"}


def get_check_repo(db: Database = Depends(get_db)) -> CheckRepo:
    return PgCheckRepo(db)


def get_bus(request: Request) -> EventBus:
    bus: EventBus = request.app.state.bus
    return bus


def get_queue(request: Request) -> CheckQueue:
    queue: CheckQueue = request.app.state.queue
    return queue


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=CheckCreated)
async def create_check(
    body: CheckIn,
    user: CurrentUser = Depends(current_user),
    repo: CheckRepo = Depends(get_check_repo),
    profiles: ProfileRepo = Depends(get_profile_repo),
    queue: CheckQueue = Depends(get_queue),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_app_settings),
) -> CheckCreated:
    try:
        url = normalize_url(body.url)
    except InvalidProductUrl as exc:
        raise HTTPException(422, detail=str(exc)) from None
    if seller_domain_for(url, await repo.seller_domains()) is None:
        raise HTTPException(422, detail="We don't support this store yet.")

    profile = await profiles.get(user.id)
    if profile is None or not profile.measurements_cm:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Save your measurements first.")
    if not await limiter.hit(f"checks:{user.id}", CHECKS_PER_WINDOW, WINDOW_S):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many checks. Try again in a few minutes."
        )
    if await repo.active_runs(user.id) >= MAX_ACTIVE_RUNS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="Wait for your current check to finish."
        )

    snapshot = ProfileSnapshot(
        unit=profile.unit.value,
        measurements_cm=profile.measurements_cm,
        brand_ids=[b.id for b in profile.brands],
    )
    run_id = await repo.create_run(
        user.id,
        input_url=url,
        profile=snapshot,
        memory=await repo.memory_snapshot(user.id),
        pipeline_version=settings.pipeline_version,
    )
    await queue.enqueue(run_id)
    return CheckCreated(id=run_id, status="queued")


@router.get("", response_model=list[CheckSummary])
async def recent_checks(
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    user: CurrentUser = Depends(current_user),
    repo: CheckRepo = Depends(get_check_repo),
) -> list[CheckSummary]:
    return await repo.recent(user.id, limit)


@router.get("/{run_id}", response_model=CheckResult)
async def read_check(
    run_id: UUID, user: CurrentUser = Depends(current_user), repo: CheckRepo = Depends(get_check_repo)
) -> CheckResult:
    result = await repo.get(user.id, run_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Check not found.")
    return result


@router.delete("/{run_id}", status_code=status.HTTP_202_ACCEPTED)
async def cancel_check(
    run_id: UUID,
    user: CurrentUser = Depends(current_user),
    repo: CheckRepo = Depends(get_check_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, str]:
    current = await repo.status(user.id, run_id)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Check not found.")
    if current not in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This check has already finished.")
    await bus.request_cancel(run_id)  # a running worker stops at its next step
    if await repo.cancel_queued(user.id, run_id):
        await bus.publish(run_id, ProgressEvent(type="cancelled", message="Check cancelled."))
    return {"status": "cancelling"}


def _sse(event_id: str | None, event: ProgressEvent) -> str:
    head = f"id: {event_id}\n" if event_id else ""
    return f"{head}event: {event.type}\ndata: {event.model_dump_json(exclude_none=True)}\n\n"


@router.get("/{run_id}/events")
async def check_events(
    run_id: UUID,
    request: Request,
    user: CurrentUser = Depends(current_user),
    repo: CheckRepo = Depends(get_check_repo),
    bus: EventBus = Depends(get_bus),
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Server-Sent Events for the loading modal. Replays from the start (or Last-Event-ID).

    EventSource can't send an Authorization header; use a fetch-based SSE client
    (e.g. @microsoft/fetch-event-source) with the Supabase access token.
    """
    if await repo.status(user.id, run_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Check not found.")

    async def stream() -> AsyncIterator[str]:
        after = last_event_id or "0"
        while not await request.is_disconnected():
            events = await bus.read(run_id, after, KEEPALIVE_MS)
            for event_id, event in events:
                after = event_id
                yield _sse(event_id, event)
                if event.type in TERMINAL:
                    return
            if not events:
                # Nothing new: the run may have ended without events (expired stream, crashed worker).
                db_status = await repo.status(user.id, run_id)
                if db_status in DB_TO_EVENT:
                    yield _sse(None, ProgressEvent(type=DB_TO_EVENT[db_status]))
                    return
                yield ": keepalive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
