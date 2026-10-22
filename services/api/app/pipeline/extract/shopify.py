"""Shopify stores: product JSON (`/products/<handle>.js`) and storefront search."""

import re
from typing import Any
from urllib.parse import quote_plus, urlsplit

from app.pipeline.fetch import Fetcher, FetchError
from app.pipeline.models import ProductExtract

_HANDLE = re.compile(r"/products/([^/?#.]+)")


def product_handle(url: str) -> str | None:
    m = _HANDLE.search(urlsplit(url).path)
    return m[1] if m else None


def _strip_html(html: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", html or "")


def parse_product_js(data: dict[str, Any], url: str, seller_domain: str) -> ProductExtract | None:
    variants = [v for v in data.get("variants") or [] if isinstance(v, dict)]
    if not data.get("title") or not variants:
        return None
    # Shopify .js prices are integer cents.
    prices = [int(v["price"]) for v in variants if isinstance(v.get("price"), int | float) and v["price"] > 0]
    sizes = []
    size_index = next(
        (
            i
            for i, opt in enumerate(data.get("options") or [])
            if str(opt.get("name", "")).lower() in ("size", "waist")
        ),
        None,
    )
    for v in variants:
        if size_index is not None and (opt := v.get(f"option{size_index + 1}")):
            sizes.append(str(opt))
    image = data.get("featured_image")
    return ProductExtract(
        url=url,
        canonical_url=url,
        seller_domain=seller_domain,
        name=str(data["title"]).strip(),
        brand=data.get("vendor"),
        category=data.get("type") or None,
        external_id=str(data.get("id")) if data.get("id") else None,
        variant_gtins=[str(v["barcode"]) for v in variants if v.get("barcode")],
        mpn=next((str(v["sku"]) for v in variants if v.get("sku")), None),
        image_url=f"https:{image}" if isinstance(image, str) and image.startswith("//") else image,
        price_cents=min(prices) if prices else 0,
        currency="USD",  # .js omits currency; storefront default. Overridden by JSON-LD when present.
        in_stock=any(bool(v.get("available")) for v in variants),
        sizes=list(dict.fromkeys(sizes)),
        attributes={"description": _strip_html(data.get("description"))[:2000]},
        extracted_by=["shopify"],
    )


async def fetch_shopify_product(fetcher: Fetcher, url: str, seller_domain: str) -> ProductExtract | None:
    handle = product_handle(url)
    if handle is None:
        return None
    host = urlsplit(url).hostname
    try:
        data = await fetcher.get_json(f"https://{host}/products/{handle}.js")
    except FetchError:
        return None
    if not isinstance(data, dict):
        return None
    product_url = f"https://{host}/products/{handle}"
    return parse_product_js(data, product_url, seller_domain)


async def search_shopify(fetcher: Fetcher, domain: str, query: str, limit: int = 5) -> list[str]:
    """Product URLs from Shopify's predictive search."""
    url = (
        f"https://{domain}/search/suggest.json?q={quote_plus(query)}"
        f"&resources[type]=product&resources[limit]={limit}"
    )
    try:
        data = await fetcher.get_json(url)
    except FetchError:
        return []
    products = (((data or {}).get("resources") or {}).get("results") or {}).get("products") or []
    urls = []
    for p in products:
        if isinstance(p, dict) and isinstance(p.get("url"), str):
            path = p["url"].split("?")[0]
            urls.append(f"https://{domain}{path}")
    return urls[:limit]
