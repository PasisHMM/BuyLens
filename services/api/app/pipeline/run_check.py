"""The check pipeline: 4 visible steps, then rank → decide → write copy → persist.

product  (Product details found)   extract the pasted listing, choose the user's size
prices   (Prices compared)         same product at other allow-listed sellers, totals, market avg
fit      (Checking your fit)       deterministic Fit Check per listing
seller   (Reviewing seller risk)   seller data + review summary (LLM, cached per listing)
"""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from app.llm import LLM
from app.pipeline import narrate, rules
from app.pipeline.cache import Cache
from app.pipeline.extract import ExtractionFailed, extract_product
from app.pipeline.fetch import Fetcher, FetchError
from app.pipeline.fitting import choose_size, evaluate_fit
from app.pipeline.models import Candidate, Match, RankedOption, SellerInfo, StepId
from app.pipeline.pricing import evaluate_prices
from app.pipeline.progress import CancelledByUser, EventBus, Progress
from app.pipeline.seller_risk import ReviewSummary, evaluate_seller, summarize_reviews
from app.pipeline.sourcing import find_candidates
from app.pipeline.store import CheckStore
from app.pipeline.urls import seller_domain_for

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineDeps:
    store: CheckStore
    bus: EventBus
    fetcher: Fetcher
    llm: LLM | None
    cache: Cache
    cache_ttl_s: int


class CheckFailed(Exception):
    """args[0] is shown to the user."""


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


async def _review_summary(deps: PipelineDeps, candidate: Candidate) -> ReviewSummary | None:
    if candidate.listing_id and (cached := await deps.store.review_summary(candidate.listing_id)):
        return cached
    if deps.llm is None:
        return None
    summary = await summarize_reviews(deps.llm, candidate.extract.review_texts)
    if summary and candidate.listing_id:
        await deps.store.save_review_summary(candidate.listing_id, summary, deps.llm.name)
    return summary


async def run_check(deps: PipelineDeps, run_id: UUID) -> None:
    run = await deps.store.load_run(run_id)
    if run is None:
        log.info("check_skipped", extra={"run_id": str(run_id)})
        return

    async def on_step(step: StepId) -> None:
        await deps.store.mark_step(run_id, step)

    progress = Progress(deps.bus, run_id, on_step)
    try:
        sellers = await deps.store.sellers()
        seller = _seller_for(run.input_url, sellers)

        async with progress.step("product") as s:
            try:
                extract = await extract_product(run.input_url, seller, fetcher=deps.fetcher, llm=deps.llm,
                                                cache=deps.cache, cache_ttl_s=deps.cache_ttl_s)  # fmt: skip
            except (ExtractionFailed, FetchError) as exc:
                raise CheckFailed(str(exc)) from exc
            brand_id = await deps.store.brand_id(extract.brand)
            source = Candidate(extract=extract, seller=seller, match=Match.EXACT, is_source=True)
            product_id, source.listing_id = await deps.store.save_listing(source, brand_id)
            size = choose_size(extract, run.profile, run.memory, brand_id)
            s.detail = ", ".join(p for p in (extract.name, extract.attributes.get("wash")) if p)

        async with progress.step("prices") as s:
            known = await deps.store.known_candidates(product_id, deps.cache_ttl_s)
            candidates = await find_candidates(source, sellers, known, fetcher=deps.fetcher, cache=deps.cache,
                                               cache_ttl_s=deps.cache_ttl_s)  # fmt: skip
            for c in candidates:
                c.is_official = (
                    c.seller.official_brand_id is not None and c.seller.official_brand_id == brand_id
                )
                if c.listing_id is None:
                    _, c.listing_id = await deps.store.save_listing(c, brand_id)
            prices = evaluate_prices(candidates)
            best_total = min(p.total_cents for p in prices.values())
            n = len(candidates)
            s.detail = f"{_money(best_total)} total across {n} seller{'s' if n != 1 else ''}"

        # The size chart comes from the product (usually the brand's page); reuse it for every
        # listing of the same product, which rarely publishes its own.
        fit_inputs = [
            c.extract.model_copy(
                update={
                    "size_chart": c.extract.size_chart or extract.size_chart,
                    "attributes": {**extract.attributes, **c.extract.attributes},
                    "category": c.extract.category or extract.category,
                }
            )
            for c in candidates
        ]

        async with progress.step("fit") as s:
            fits = [evaluate_fit(f, size, run.profile, run.memory, brand_id) for f in fit_inputs]
            compared = [r.dimension for r in fits[0].rows if r.garment_cm is not None]
            s.detail = (
                f"{', '.join(compared).capitalize()} compared" if compared else "No comparable size data"
            )

        async with progress.step("seller") as s:
            summaries = await asyncio.gather(*(_review_summary(deps, c) for c in candidates))
            risks = [evaluate_seller(c, summary) for c, summary in zip(candidates, summaries, strict=True)]
            s.detail = "Reviews and return policy checked"

        options = []
        for i, c in enumerate(candidates):
            if risks[i].fit_signal in ("runs_small", "runs_large"):  # reviews refine the fit card
                fits[i] = evaluate_fit(
                    fit_inputs[i], size, run.profile, run.memory, brand_id, risks[i].fit_signal
                )
            score = rules.score(prices[i], fits[i], risks[i], run.memory.decision)
            options.append(
                RankedOption(rank=0, candidate=c, price=prices[i], fit=fits[i], risk=risks[i], score=score)
            )
        ranked = rules.rank(options)
        decision = rules.decide(ranked[0], run.memory.decision)
        copy = await narrate.write_copy(deps.llm, extract, ranked, decision)

        await deps.store.complete_run(run_id, product_id, size, ranked, decision, copy)
        await progress.finish("complete")
        log.info("check_done", extra={"run_id": str(run_id), "verdict": decision.verdict.value,
                                      "options": len(ranked), "copy": copy.written_by})  # fmt: skip
    except CancelledByUser:
        await deps.store.finish_run(run_id, "cancelled")
        await progress.finish("cancelled", "Check cancelled.")
    except CheckFailed as exc:
        await deps.store.finish_run(run_id, "failed", str(exc))
        await progress.finish("failed", str(exc))
    except Exception:
        log.exception("check_crashed", extra={"run_id": str(run_id)})
        message = "Something went wrong on our side. Please try again."
        await deps.store.finish_run(run_id, "failed", message)
        await progress.finish("failed", message)


def _seller_for(url: str, sellers: list[SellerInfo]) -> SellerInfo:
    domain = seller_domain_for(url, [s.domain for s in sellers])
    seller = next((s for s in sellers if s.domain == domain), None)
    if seller is None:
        raise CheckFailed("We don't support this store yet.")
    return seller
