"""API-side access to check runs. Everything runs under RLS as the calling user."""

from typing import Any, Protocol
from uuid import UUID

from app.db import Database
from app.pipeline.models import FitCheck, MemorySnapshot, PriceCheck, ProfileSnapshot, SellerRisk
from app.schemas.checks import CheckResult, CheckSummary, OptionOut, ProductOut, SellerOut, WhyNot


class CheckRepo(Protocol):
    async def seller_domains(self) -> list[str]: ...
    async def memory_snapshot(self, user_id: UUID) -> MemorySnapshot: ...
    async def active_runs(self, user_id: UUID) -> int: ...
    async def create_run(self, user_id: UUID, *, input_url: str, profile: ProfileSnapshot,
                         memory: MemorySnapshot, pipeline_version: str) -> UUID: ...  # fmt: skip
    async def status(self, user_id: UUID, run_id: UUID) -> str | None: ...
    async def get(self, user_id: UUID, run_id: UUID) -> CheckResult | None: ...
    async def recent(self, user_id: UUID, limit: int) -> list[CheckSummary]: ...
    async def cancel_queued(self, user_id: UUID, run_id: UUID) -> bool: ...


_GET_RUN = """
select r.id, r.status, r.current_step, r.input_url, r.created_at, r.completed_at, r.error,
       r.profile_snapshot ->> 'unit' as unit, r.selected_size, r.verdict, r.headline, r.explanation,
       r.why_not, p.name as product_name, p.category, p.attributes, p.image_url
  from check_runs r left join products p on p.id = r.product_id
 where r.id = $1
"""

_GET_OPTIONS = """
select o.rank, o.total_cents, o.summary, o.price_check, o.fit_check, o.seller_risk,
       l.url, s.name as seller_name, s.domain
  from check_options o
  join listings l on l.id = o.listing_id
  join sellers s on s.id = l.seller_id
 where o.run_id = $1
 order by o.rank
"""

_RECENT = """
select r.id, r.status, r.created_at, r.verdict, r.selected_size, p.name as product_name, p.image_url,
       o.total_cents, o.price_check ->> 'currency' as currency
  from check_runs r
  left join products p on p.id = r.product_id
  left join check_options o on o.run_id = r.id and o.rank = 1
 where r.user_id = $1
 order by r.created_at desc
 limit $2
"""


class PgCheckRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def seller_domains(self) -> list[str]:
        async with self._db.public_tx() as conn:
            rows = await conn.fetch("select domain from sellers where enabled")
        return [r["domain"] for r in rows]

    async def memory_snapshot(self, user_id: UUID) -> MemorySnapshot:
        async with self._db.user_tx(user_id) as conn:
            fit = await conn.fetch("select brand_id, category, dimension, ease_adjust_cm from fit_memory")
            decision = await conn.fetchrow(
                "select price_sensitivity, risk_aversion, fit_strictness from decision_memory"
            )
        return MemorySnapshot.model_validate(
            {
                "fit": [{**dict(r), "ease_adjust_cm": float(r["ease_adjust_cm"])} for r in fit],
                "decision": {k: float(v) for k, v in dict(decision).items()} if decision else {},
            }
        )

    async def active_runs(self, user_id: UUID) -> int:
        async with self._db.user_tx(user_id) as conn:
            count: int = await conn.fetchval(
                """
                select count(*) from check_runs
                 where status in ('queued', 'running') and created_at > now() - interval '5 minutes'
                """
            )
        return count

    async def create_run(self, user_id: UUID, *, input_url: str, profile: ProfileSnapshot,
                         memory: MemorySnapshot, pipeline_version: str) -> UUID:  # fmt: skip
        async with self._db.user_tx(user_id) as conn:
            run_id: UUID = await conn.fetchval(
                """
                insert into check_runs (user_id, input_url, profile_snapshot, memory_snapshot,
                                        pipeline_version)
                values ($1, $2, $3, $4, $5) returning id
                """,
                user_id,
                input_url,
                profile.model_dump(mode="json"),
                memory.model_dump(mode="json"),
                pipeline_version,
            )
        return run_id

    async def status(self, user_id: UUID, run_id: UUID) -> str | None:
        async with self._db.user_tx(user_id) as conn:
            value: str | None = await conn.fetchval(
                "select status::text from check_runs where id = $1", run_id
            )
        return value

    async def get(self, user_id: UUID, run_id: UUID) -> CheckResult | None:
        async with self._db.user_tx(user_id) as conn:
            run = await conn.fetchrow(_GET_RUN, run_id)
            if run is None:
                return None
            options = await conn.fetch(_GET_OPTIONS, run_id)
        return _result(run, options)

    async def recent(self, user_id: UUID, limit: int) -> list[CheckSummary]:
        async with self._db.user_tx(user_id) as conn:
            rows = await conn.fetch(_RECENT, user_id, limit)
        return [CheckSummary.model_validate(dict(r)) for r in rows]

    async def cancel_queued(self, user_id: UUID, run_id: UUID) -> bool:
        async with self._db.user_tx(user_id) as conn:
            result: str = await conn.execute(
                """
                update check_runs set status = 'cancelled', completed_at = now()
                 where id = $1 and status = 'queued'
                """,
                run_id,
            )
        return result.endswith(" 1")


def _result(run: Any, options: list[Any]) -> CheckResult:
    attributes = dict(run["attributes"] or {})
    product = None
    if run["product_name"]:
        product = ProductOut(
            name=run["product_name"],
            brand=attributes.pop("brand_name", None),
            category=run["category"],
            attributes=attributes,
            image_url=run["image_url"],
        )
    why_not = run["why_not"] or None
    return CheckResult(
        id=run["id"],
        status=run["status"],
        current_step=run["current_step"],
        input_url=run["input_url"],
        created_at=run["created_at"],
        completed_at=run["completed_at"],
        error=run["error"],
        unit=run["unit"] or "in",
        product=product,
        selected_size=run["selected_size"],
        verdict=run["verdict"],
        headline=run["headline"],
        explanation=run["explanation"],
        why_not=WhyNot(buy=why_not.get("buy"), skip=why_not.get("skip")) if why_not else None,
        options=[
            OptionOut(
                rank=o["rank"],
                seller=SellerOut(name=o["seller_name"], domain=o["domain"]),
                url=o["url"],
                total_cents=o["total_cents"],
                summary=o["summary"],
                price_check=PriceCheck.model_validate(o["price_check"]),
                fit_check=FitCheck.model_validate(o["fit_check"]),
                seller_risk=SellerRisk.model_validate(o["seller_risk"]),
            )
            for o in options
        ],
    )
