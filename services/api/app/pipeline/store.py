"""Worker-side persistence (service role). User data is always addressed by run id."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.db import Conn, Database
from app.pipeline.models import (
    Candidate,
    Decision,
    Match,
    MemorySnapshot,
    Narrative,
    ProductExtract,
    ProfileSnapshot,
    RankedOption,
    ReturnPolicy,
    SellerInfo,
    ShippingPolicy,
    SizeChoice,
    StepId,
)
from app.pipeline.seller_risk import ReviewSummary


@dataclass(frozen=True, slots=True)
class RunRecord:
    id: UUID
    user_id: UUID
    input_url: str
    status: str
    profile: ProfileSnapshot
    memory: MemorySnapshot


class CheckStore(Protocol):
    async def load_run(self, run_id: UUID) -> RunRecord | None: ...
    async def sellers(self) -> list[SellerInfo]: ...
    async def mark_step(self, run_id: UUID, step: StepId) -> None: ...
    async def brand_id(self, brand: str | None) -> UUID | None: ...
    async def save_listing(self, candidate: Candidate, brand_id: UUID | None) -> tuple[UUID, UUID]: ...
    async def known_candidates(self, product_id: UUID, max_age_s: int) -> list[Candidate]: ...
    async def review_summary(self, listing_id: UUID) -> ReviewSummary | None: ...
    async def save_review_summary(self, listing_id: UUID, summary: ReviewSummary, model: str) -> None: ...
    async def complete_run(
        self,
        run_id: UUID,
        product_id: UUID,
        size: SizeChoice | None,
        options: list[RankedOption],
        decision: Decision,
        narrative: Narrative,
    ) -> None: ...
    async def finish_run(self, run_id: UUID, status: str, error: str | None = None) -> None: ...


SELLER_COLUMNS = (
    "s.id, s.name, s.domain, s.official_brand, s.adapter, s.trust_rating, s.return_policy, s.shipping_policy"
)


def seller_from_row(row: Any) -> SellerInfo:
    return SellerInfo(
        id=row["id"],
        name=row["name"],
        domain=row["domain"],
        official_brand_id=row["official_brand"],
        adapter=row["adapter"],
        trust_rating=float(row["trust_rating"]) if row["trust_rating"] is not None else None,
        return_policy=ReturnPolicy.model_validate(row["return_policy"] or {}),
        shipping_policy=ShippingPolicy.model_validate(row["shipping_policy"] or {}),
    )


_INSERT_PRODUCT = """
insert into products (brand_id, name, category, gtin, mpn, attributes, image_url)
values ($1, $2, $3, $4, $5, $6, $7)
on conflict (brand_id, mpn) where mpn is not null do update set name = excluded.name
returning id
"""

_UPSERT_LISTING = """
insert into listings (product_id, seller_id, url, canonical_url, currency, price_cents, shipping_cents,
                      in_stock, sizes, size_chart, review_rating, review_count, external_id, extract,
                      fetched_at)
values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, now())
on conflict (product_id, seller_id) do update set
    url = excluded.url, canonical_url = excluded.canonical_url, currency = excluded.currency,
    price_cents = excluded.price_cents, shipping_cents = excluded.shipping_cents,
    in_stock = excluded.in_stock, sizes = excluded.sizes, size_chart = excluded.size_chart,
    review_rating = excluded.review_rating, review_count = excluded.review_count,
    external_id = excluded.external_id, extract = excluded.extract, fetched_at = now()
returning id
"""

_INSERT_OPTION = """
insert into check_options (run_id, rank, listing_id, total_cents, score, summary,
                           price_check, fit_check, seller_risk)
values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""

_COMPLETE_RUN = """
update check_runs
   set status = 'done', current_step = null, product_id = $2, selected_size = $3, verdict = $4,
       headline = $5, explanation = $6, why_not = $7, completed_at = now()
 where id = $1
"""


class PgCheckStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def load_run(self, run_id: UUID) -> RunRecord | None:
        """Claim a queued run. None if unknown, already claimed, or cancelled before it started."""
        async with self._db.service_tx() as conn:
            row = await conn.fetchrow(
                """
                update check_runs set status = 'running'
                 where id = $1 and status = 'queued'
                returning id, user_id, input_url, status, profile_snapshot, memory_snapshot
                """,
                run_id,
            )
        if row is None:
            return None
        return RunRecord(
            id=row["id"],
            user_id=row["user_id"],
            input_url=row["input_url"],
            status=row["status"],
            profile=ProfileSnapshot.model_validate(row["profile_snapshot"]),
            memory=MemorySnapshot.model_validate(row["memory_snapshot"] or {}),
        )

    async def sellers(self) -> list[SellerInfo]:
        async with self._db.service_tx() as conn:
            rows = await conn.fetch(f"select {SELLER_COLUMNS} from sellers s where s.enabled")  # noqa: S608
        return [seller_from_row(r) for r in rows]

    async def mark_step(self, run_id: UUID, step: StepId) -> None:
        async with self._db.service_tx() as conn:
            await conn.execute(
                "update check_runs set current_step = $2 where id = $1 and status = 'running'", run_id, step
            )

    async def brand_id(self, brand: str | None) -> UUID | None:
        if not brand:
            return None
        async with self._db.service_tx() as conn:
            value: UUID | None = await conn.fetchval(
                "select id from brands where lower(name) = lower($1) or slug = lower($1) limit 1",
                brand.strip(),
            )
        return value

    async def _product_id(self, conn: Conn, e: ProductExtract, brand_id: UUID | None) -> UUID:
        """Same listing URL → same product; then GTIN; then brand + MPN; else a new product."""
        lookups: list[tuple[str, tuple[Any, ...]]] = [
            ("select product_id from listings where canonical_url = $1", (e.canonical_url,)),
        ]
        if e.gtin:
            lookups.append(("select id from products where gtin = $1 limit 1", (e.gtin,)))
        if e.mpn and brand_id:
            lookups.append(("select id from products where brand_id = $1 and mpn = $2", (brand_id, e.mpn)))
        for sql, args in lookups:
            if pid := await conn.fetchval(sql, *args):
                return pid  # type: ignore[no-any-return]

        attributes = {k: v for k, v in {**e.attributes, "brand_name": e.brand}.items() if k != "description"}
        pid = await conn.fetchval(
            _INSERT_PRODUCT,
            brand_id,
            e.name,
            e.category or "unknown",
            e.gtin,
            e.mpn if brand_id else None,
            attributes,
            e.image_url,
        )
        return pid  # type: ignore[no-any-return]

    async def save_listing(self, candidate: Candidate, brand_id: UUID | None) -> tuple[UUID, UUID]:
        e = candidate.extract
        size_chart = e.size_chart.model_dump(mode="json") if e.size_chart else None
        async with self._db.service_tx() as conn:
            product_id = await self._product_id(conn, e, brand_id)
            listing_id = await conn.fetchval(
                _UPSERT_LISTING,
                product_id,
                candidate.seller.id,
                e.url,
                e.canonical_url,
                e.currency,
                e.price_cents,
                e.shipping_cents,
                e.in_stock,
                e.sizes,
                size_chart,
                e.review_rating,
                e.review_count,
                e.external_id,
                e.model_dump(mode="json"),
            )
        return product_id, listing_id

    async def known_candidates(self, product_id: UUID, max_age_s: int) -> list[Candidate]:
        async with self._db.service_tx() as conn:
            rows = await conn.fetch(
                f"""
                select l.id as listing_id, l.extract, {SELLER_COLUMNS}
                  from listings l join sellers s on s.id = l.seller_id
                 where l.product_id = $1 and s.enabled and l.extract is not null
                   and l.fetched_at > now() - make_interval(secs => $2)
                """,  # noqa: S608
                product_id,
                float(max_age_s),
            )
        return [
            Candidate(
                extract=ProductExtract.model_validate(r["extract"]),
                seller=seller_from_row(r),
                match=Match.EXACT,  # stored under the same product id
                listing_id=r["listing_id"],
            )
            for r in rows
        ]

    async def review_summary(self, listing_id: UUID) -> ReviewSummary | None:
        async with self._db.service_tx() as conn:
            raw = await conn.fetchval(
                "select summary from review_summaries where listing_id = $1", listing_id
            )
        return ReviewSummary.model_validate(raw) if raw else None

    async def save_review_summary(self, listing_id: UUID, summary: ReviewSummary, model: str) -> None:
        async with self._db.service_tx() as conn:
            await conn.execute(
                """
                insert into review_summaries (listing_id, summary, model) values ($1, $2, $3)
                on conflict (listing_id) do update
                   set summary = excluded.summary, model = excluded.model, created_at = now()
                """,
                listing_id,
                summary.model_dump(mode="json"),
                model,
            )

    async def complete_run(
        self,
        run_id: UUID,
        product_id: UUID,
        size: SizeChoice | None,
        options: list[RankedOption],
        decision: Decision,
        narrative: Narrative,
    ) -> None:
        async with self._db.service_tx() as conn:
            status = await conn.fetchval("select status from check_runs where id = $1 for update", run_id)
            if status != "running":
                return  # cancelled while finishing
            await conn.execute("delete from check_options where run_id = $1", run_id)
            for option, summary in zip(options, narrative.option_summaries, strict=True):
                await conn.execute(
                    _INSERT_OPTION,
                    run_id,
                    option.rank,
                    option.candidate.listing_id,
                    option.price.total_cents,
                    option.score,
                    summary,
                    option.price.model_dump(mode="json"),
                    option.fit.model_dump(mode="json"),
                    option.risk.model_dump(mode="json"),
                )
            why_not = {
                "buy": narrative.why_not_buy,
                "skip": narrative.why_not_skip,
                "reasons": decision.reasons,
                "written_by": narrative.written_by,
            }
            await conn.execute(
                _COMPLETE_RUN,
                run_id,
                product_id,
                size.display if size else None,
                decision.verdict.value,
                narrative.headline,
                narrative.explanation,
                why_not,
            )

    async def finish_run(self, run_id: UUID, status: str, error: str | None = None) -> None:
        async with self._db.service_tx() as conn:
            await conn.execute(
                """
                update check_runs set status = $2::run_status, error = $3, current_step = null,
                                      completed_at = now()
                 where id = $1 and status in ('queued', 'running')
                """,
                run_id,
                status,
                error,
            )
