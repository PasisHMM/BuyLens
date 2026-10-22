"""Find the same product at other allow-listed sellers.

Search needs a per-seller adapter. Today only Shopify storefronts have one; sellers with the
generic `jsonld` adapter can still contribute listings found earlier (stored in the DB).
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from difflib import SequenceMatcher

from app.pipeline.cache import Cache
from app.pipeline.extract import ExtractionFailed, extract_product
from app.pipeline.extract.shopify import search_shopify
from app.pipeline.fetch import Fetcher, FetchError
from app.pipeline.models import Candidate, Match, ProductExtract, SellerInfo

NAME_SIMILARITY = 0.85
RESULTS_PER_SELLER = 3
SELLER_TIMEOUT_S = 15.0

SearchFn = Callable[[Fetcher, str, str], Awaitable[list[str]]]
SEARCH_ADAPTERS: dict[str, SearchFn] = {"shopify": search_shopify}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(text: str | None) -> str:
    return _NON_ALNUM.sub(" ", (text or "").lower().replace("®", "").replace("™", "")).strip()


def _name_key(extract: ProductExtract) -> str:
    name = _norm(extract.name)
    brand = _norm(extract.brand)
    if brand and name.startswith(brand):
        name = name[len(brand) :].strip()
    return name


def _gtins(extract: ProductExtract) -> set[str]:
    return {g.lstrip("0") for g in [extract.gtin, *extract.variant_gtins] if g}


def match_product(source: ProductExtract, other: ProductExtract) -> Match | None:
    if _gtins(source) & _gtins(other):
        return Match.EXACT
    same_brand = bool(source.brand and other.brand and _norm(source.brand) == _norm(other.brand))
    if same_brand and source.mpn and other.mpn and _norm(source.mpn) == _norm(other.mpn):
        return Match.EXACT
    if not same_brand:
        return None
    if source.color and other.color and _norm(source.color) != _norm(other.color):
        return None
    if SequenceMatcher(None, _name_key(source), _name_key(other)).ratio() >= NAME_SIMILARITY:
        return Match.LIKELY
    return None


def search_query(extract: ProductExtract) -> str:
    return " ".join(p for p in (extract.brand, _name_key(extract)) if p)


async def _search_seller(source: ProductExtract, seller: SellerInfo, *, fetcher: Fetcher, cache: Cache,
                         cache_ttl_s: int) -> Candidate | None:  # fmt: skip
    search = SEARCH_ADAPTERS[seller.adapter]
    try:
        urls = await search(fetcher, seller.domain, search_query(source))
    except FetchError:
        return None
    for url in urls[:RESULTS_PER_SELLER]:
        try:
            # No LLM while sourcing: comparables must come from structured data.
            other = await extract_product(
                url, seller, fetcher=fetcher, llm=None, cache=cache, cache_ttl_s=cache_ttl_s
            )
        except (ExtractionFailed, FetchError):
            continue
        if (match := match_product(source, other)) is not None:
            return Candidate(extract=other, seller=seller, match=match)
    return None


async def find_candidates(source: Candidate, sellers: list[SellerInfo], known: list[Candidate], *,
                          fetcher: Fetcher, cache: Cache, cache_ttl_s: int) -> list[Candidate]:  # fmt: skip
    """Source listing first, then one listing per other seller (fresh search beats stored listing)."""
    by_seller: dict[str, Candidate] = {
        c.seller.domain: c for c in known if c.seller.domain != source.seller.domain
    }

    searchable = [s for s in sellers if s.domain != source.seller.domain and s.adapter in SEARCH_ADAPTERS]

    async def bounded(seller: SellerInfo) -> Candidate | None:
        try:
            return await asyncio.wait_for(
                _search_seller(source.extract, seller, fetcher=fetcher, cache=cache, cache_ttl_s=cache_ttl_s),
                timeout=SELLER_TIMEOUT_S,
            )
        except TimeoutError:
            return None

    for found in await asyncio.gather(*(bounded(s) for s in searchable)):
        if found is not None:
            by_seller[found.seller.domain] = found
    return [source, *by_seller.values()]
