"""Product extraction: cheapest reliable source first, the LLM only for what's still missing.

seller adapter (Shopify JSON) → JSON-LD → OpenGraph meta → HTML size-chart table → LLM
"""

import contextlib
import re

from app.llm import LLM
from app.pipeline.cache import Cache
from app.pipeline.extract.attributes import infer_category, infer_fit, infer_stretch, infer_wash
from app.pipeline.extract.jsonld import apply_meta_fallbacks, canonical_link, extract_jsonld
from app.pipeline.extract.llm import llm_extract
from app.pipeline.extract.shopify import fetch_shopify_product
from app.pipeline.extract.sizechart import find_size_chart
from app.pipeline.extract.text import clean_text, soup_of
from app.pipeline.fetch import Fetcher, FetchError
from app.pipeline.models import ProductExtract, SellerInfo
from app.pipeline.urls import InvalidProductUrl, domain_matches, host_of, normalize_url

SIZE_CHART_HINT = re.compile(r"size (chart|guide)|waist|inseam", re.IGNORECASE)


class ExtractionFailed(Exception):
    """args[0] is a user-safe message."""


def _merge(primary: ProductExtract, extra: ProductExtract | None) -> ProductExtract:
    """Fill unset fields of `primary` from `extra`."""
    if extra is None:
        return primary
    merged = primary.model_copy(deep=True)
    for field in ("brand", "category", "gtin", "mpn", "external_id", "color", "image_url", "shipping_cents",
                  "in_stock", "review_rating", "review_count", "size_chart"):  # fmt: skip
        if getattr(merged, field) is None:
            setattr(merged, field, getattr(extra, field))
    merged.variant_gtins = merged.variant_gtins or extra.variant_gtins
    if not merged.price_cents:
        merged.price_cents, merged.currency = extra.price_cents, extra.currency
    merged.name = merged.name or extra.name
    merged.sizes = merged.sizes or extra.sizes
    merged.review_texts = merged.review_texts or extra.review_texts
    merged.attributes = {**extra.attributes, **merged.attributes}
    merged.extracted_by = list(dict.fromkeys(merged.extracted_by + extra.extracted_by))
    return merged


def _enrich(extract: ProductExtract) -> ProductExtract:
    attrs = extract.attributes
    description = attrs.get("description")
    texts = (extract.name, extract.color, description)
    extract.category = extract.category or infer_category(extract.name, description)
    if (category := infer_category(extract.category)) is not None:
        extract.category = category  # normalize "Women's Jeans" → "jeans"
    if "stretch" not in attrs:
        attrs["stretch"] = infer_stretch(attrs.get("fabric"), *texts)
    attrs.setdefault("fit", infer_fit(*texts))
    attrs.setdefault("wash", infer_wash(*texts))
    extract.attributes = {k: v for k, v in attrs.items() if v is not None}
    return extract


async def extract_product(
    url: str, seller: SellerInfo, *, fetcher: Fetcher, llm: LLM | None, cache: Cache, cache_ttl_s: int
) -> ProductExtract:
    if cached := await cache.get(f"extract:{url}"):
        return ProductExtract.model_validate_json(cached)

    adapter_result = None
    if seller.adapter == "shopify":
        adapter_result = await fetch_shopify_product(fetcher, url, seller.domain)

    try:
        page = await fetcher.get_page(url)
    except FetchError as exc:
        if adapter_result is None or not adapter_result.is_sufficient():
            raise ExtractionFailed(str(exc)) from exc
        return _enrich(adapter_result)

    soup = soup_of(page.text)
    canonical = url
    if (link := canonical_link(soup)) and domain_matches(host_of(link), seller.domain):
        with contextlib.suppress(InvalidProductUrl):
            canonical = normalize_url(link)

    structured = apply_meta_fallbacks(extract_jsonld(url, canonical, seller.domain, soup), url, canonical,
                                      seller.domain, soup)  # fmt: skip
    extract = _merge(adapter_result, structured) if adapter_result else structured
    if extract is None:
        extract = ProductExtract(url=url, canonical_url=canonical, seller_domain=seller.domain, name="")
    extract.canonical_url = canonical
    extract.size_chart = extract.size_chart or find_size_chart(soup)

    needs_llm = not extract.is_sufficient() or (
        extract.size_chart is None and SIZE_CHART_HINT.search(page.text)
    )
    if needs_llm and llm is not None:
        extract = await llm_extract(llm, clean_text(page.text), extract)

    if not extract.is_sufficient():
        raise ExtractionFailed("We couldn't read the product name and price on that page.")
    extract = _enrich(extract)
    await cache.set(f"extract:{url}", extract.model_dump_json(), cache_ttl_s)
    return extract
