"""In-memory stand-ins for the pipeline's external dependencies."""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.llm import LLMError
from app.pipeline.fetch import FetchError, Page
from app.pipeline.models import (
    Candidate,
    Decision,
    MemorySnapshot,
    Narrative,
    ProfileSnapshot,
    RankedOption,
    ReturnPolicy,
    SellerInfo,
    ShippingPolicy,
    SizeChoice,
    StepId,
)
from app.pipeline.seller_risk import ReviewSummary
from app.pipeline.store import RunRecord

FIXTURES = Path(__file__).parent / "fixtures"
IN = 2.54
DESIGN_PROFILE = ProfileSnapshot(
    unit="in",
    measurements_cm={"waist": round(26 * IN, 1), "inseam": round(30 * IN, 1), "hips": round(36 * IN, 1)},
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def seller(domain: str, *, name: str | None = None, adapter: str = "jsonld", official_brand_id: UUID | None = None,
           trust: float | None = None, returns: ReturnPolicy | None = None,
           shipping: ShippingPolicy | None = None) -> SellerInfo:  # fmt: skip
    return SellerInfo(
        id=uuid4(),
        name=name or domain,
        domain=domain,
        official_brand_id=official_brand_id,
        adapter=adapter,
        trust_rating=trust,
        return_policy=returns or ReturnPolicy(),
        shipping_policy=shipping or ShippingPolicy(),
    )


class FakeLLM:
    """Answers by schema type. A response may be a model instance, a callable(prompt) or an Exception."""

    name = "fake"

    def __init__(self, responses: dict[type[BaseModel], Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, type[BaseModel], str]] = []

    async def structured(
        self, *, tier: str, system: str, prompt: str, schema: type[Any], max_tokens: int = 1024
    ) -> Any:
        self.calls.append((tier, schema, prompt))
        response = self.responses.get(schema)
        if response is None:
            raise LLMError(f"no fake response for {schema.__name__}")
        if isinstance(response, Exception):
            raise response
        if callable(response) and not isinstance(response, BaseModel):
            response = response(prompt)
        return response


class FakeFetcher:
    def __init__(self, pages: dict[str, str] | None = None, json: dict[str, Any] | None = None) -> None:
        self.pages = pages or {}
        self.json = json or {}
        self.requested: list[str] = []

    async def get_page(self, url: str) -> Page:
        self.requested.append(url)
        if url not in self.pages:
            raise FetchError("That product page doesn't exist anymore.")
        return Page(url=url, status=200, text=self.pages[url], content_type="text/html")

    async def get_json(self, url: str) -> Any:
        self.requested.append(url)
        if url not in self.json:
            raise FetchError("not found")
        return self.json[url]

    async def aclose(self) -> None:
        pass


class MemoryStore:
    def __init__(self, sellers: list[SellerInfo], profile: ProfileSnapshot = DESIGN_PROFILE,
                 memory: MemorySnapshot | None = None, brands: dict[str, UUID] | None = None) -> None:  # fmt: skip
        self._sellers = sellers
        self.brands = brands or {}
        self.runs: dict[UUID, dict[str, Any]] = {}
        self.listings: dict[UUID, Candidate] = {}
        self.listing_product: dict[UUID, UUID] = {}
        self.products: dict[str, UUID] = {}
        self.summaries: dict[UUID, ReviewSummary] = {}
        self.steps: list[StepId] = []
        self.profile = profile
        self.memory = memory or MemorySnapshot()
        self.on_step: Callable[[StepId], None] | None = None

    def add_run(self, url: str, status: str = "queued") -> UUID:
        run_id = uuid4()
        self.runs[run_id] = {"input_url": url, "status": status, "user_id": uuid4()}
        return run_id

    async def load_run(self, run_id: UUID) -> RunRecord | None:
        run = self.runs.get(run_id)
        if run is None or run["status"] != "queued":
            return None
        run["status"] = "running"
        return RunRecord(id=run_id, user_id=run["user_id"], input_url=run["input_url"], status="running",
                         profile=self.profile, memory=self.memory)  # fmt: skip

    async def sellers(self) -> list[SellerInfo]:
        return self._sellers

    async def mark_step(self, run_id: UUID, step: StepId) -> None:
        self.steps.append(step)
        if self.on_step:
            self.on_step(step)

    async def brand_id(self, brand: str | None) -> UUID | None:
        return self.brands.get((brand or "").lower())

    async def save_listing(self, candidate: Candidate, brand_id: UUID | None) -> tuple[UUID, UUID]:
        key = candidate.extract.canonical_url
        product_id = self.products.setdefault(key, uuid4())
        listing_id = uuid4()
        self.listings[listing_id] = candidate
        self.listing_product[listing_id] = product_id
        return product_id, listing_id

    async def known_candidates(self, product_id: UUID, max_age_s: int) -> list[Candidate]:
        return []

    async def review_summary(self, listing_id: UUID) -> ReviewSummary | None:
        return self.summaries.get(listing_id)

    async def save_review_summary(self, listing_id: UUID, summary: ReviewSummary, model: str) -> None:
        self.summaries[listing_id] = summary

    async def complete_run(self, run_id: UUID, product_id: UUID, size: SizeChoice | None,
                           options: list[RankedOption], decision: Decision,
                           narrative: Narrative) -> None:  # fmt: skip
        run = self.runs[run_id]
        if run["status"] != "running":
            return
        run.update(status="done", size=size, options=options, decision=decision, narrative=narrative)

    async def finish_run(self, run_id: UUID, status: str, error: str | None = None) -> None:
        run = self.runs[run_id]
        if run["status"] in ("queued", "running"):
            run.update(status=status, error=error)
