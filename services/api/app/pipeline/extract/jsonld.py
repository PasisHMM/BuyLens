"""schema.org/Product from JSON-LD, with OpenGraph / product meta tags as a price fallback."""

import json
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup

from app.pipeline.extract.text import attr_str, to_cents, to_float
from app.pipeline.models import ProductExtract

GTIN_KEYS = ("gtin13", "gtin12", "gtin14", "gtin8", "gtin")
IN_STOCK = ("instock", "limitedavailability", "onlinesonly", "instoreonly", "presale", "preorder")


def _iter_nodes(data: Any) -> Iterator[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _iter_nodes(data["@graph"])


def _types(node: dict[str, Any]) -> set[str]:
    t = node.get("@type", [])
    return {str(x).rsplit("/", 1)[-1].lower() for x in (t if isinstance(t, list) else [t])}


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _text(value: Any) -> str | None:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("name") or value.get("@value") or value.get("url")
    return str(value).strip() if value not in (None, "") else None


def product_nodes(soup: BeautifulSoup) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "null", strict=False)
        except json.JSONDecodeError:
            continue
        nodes.extend(n for n in _iter_nodes(data) if _types(n) & {"product", "productgroup"})
    return nodes


def _offers(node: dict[str, Any]) -> list[dict[str, Any]]:
    offers = node.get("offers")
    out = [o for o in (offers if isinstance(offers, list) else [offers]) if isinstance(o, dict)]
    for o in list(out):
        if "aggregateoffer" in _types(o) and isinstance(o.get("offers"), list):
            out.extend(x for x in o["offers"] if isinstance(x, dict))
    return out


def _price_cents(offer: dict[str, Any]) -> int | None:
    for key in ("price", "lowPrice"):
        if (cents := to_cents(_first(offer.get(key)))) is not None and cents > 0:
            return cents
    spec = _first(offer.get("priceSpecification"))
    if isinstance(spec, dict):
        return to_cents(spec.get("price"))
    return None


def _shipping_cents(offer: dict[str, Any]) -> int | None:
    details = _first(offer.get("shippingDetails"))
    if isinstance(details, dict):
        rate = _first(details.get("shippingRate"))
        if isinstance(rate, dict):
            return to_cents(rate.get("value"))
    return None


def _variant_sizes(node: dict[str, Any]) -> list[str]:
    sizes: list[str] = []
    for variant in node.get("hasVariant") or []:
        if isinstance(variant, dict) and (size := _text(variant.get("size"))):
            sizes.append(size)
    return list(dict.fromkeys(sizes))


def extract_jsonld(
    url: str, canonical_url: str, seller_domain: str, soup: BeautifulSoup
) -> ProductExtract | None:
    nodes = product_nodes(soup)
    if not nodes:
        return None
    # Prefer the ProductGroup (it carries variants), then the node with the most offers.
    node = max(nodes, key=lambda n: ("productgroup" in _types(n), len(_offers(n))))
    variants = [v for v in node.get("hasVariant") or [] if isinstance(v, dict)]
    offers = _offers(node) or [o for v in variants for o in _offers(v)]

    prices = [c for o in offers if (c := _price_cents(o))]
    currency = next((str(o["priceCurrency"]).upper() for o in offers if o.get("priceCurrency")), None)
    availability = [str(o.get("availability", "")).rsplit("/", 1)[-1].lower() for o in offers]
    shipping = next((c for o in offers if (c := _shipping_cents(o)) is not None), None)

    raw_rating = node.get("aggregateRating")
    rating: dict[str, Any] = raw_rating if isinstance(raw_rating, dict) else {}
    count = to_float(rating.get("reviewCount") or rating.get("ratingCount"))
    reviews = [r for r in (node.get("review") or []) if isinstance(r, dict)]
    gtin = next((_text(node.get(k)) for k in GTIN_KEYS if node.get(k)), None)
    variant_gtins = [g for v in variants for k in GTIN_KEYS if (g := _text(v.get(k)))]

    extract = ProductExtract(
        url=url,
        canonical_url=canonical_url,
        seller_domain=seller_domain,
        name=_text(node.get("name")) or "",
        brand=_text(node.get("brand")),
        mpn=_text(node.get("mpn")) or _text(node.get("productGroupID")) or _text(node.get("sku")),
        gtin=gtin,
        variant_gtins=list(dict.fromkeys(variant_gtins)),
        color=_text(node.get("color")),
        image_url=_text(node.get("image")),
        attributes={
            k: v
            for k, v in {
                "fabric": _text(node.get("material")),
                "description": (_text(node.get("description")) or "")[:2000],
            }.items()
            if v
        },
        price_cents=min(prices) if prices else 0,
        currency=currency or "USD",
        shipping_cents=shipping,
        in_stock=any(a in IN_STOCK for a in availability) if availability else None,
        sizes=_variant_sizes(node) or [s for s in [_text(node.get("size"))] if s],
        review_rating=to_float(rating.get("ratingValue")),
        review_count=int(count) if count else None,
        review_texts=[t for r in reviews[:20] if (t := _text(r.get("reviewBody")))],
        extracted_by=["jsonld"],
    )
    return extract


def apply_meta_fallbacks(extract: ProductExtract | None, url: str, canonical_url: str, seller_domain: str,
                         soup: BeautifulSoup) -> ProductExtract | None:  # fmt: skip
    """Fill name/price/image from OpenGraph and product meta tags when JSON-LD is missing or thin."""

    def meta(*names: str) -> str | None:
        for name in names:
            tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            if tag and (value := attr_str(tag, "content")):
                return value
        return None

    price = to_cents(meta("product:price:amount", "og:price:amount"))
    title = meta("og:title")
    if extract is None:
        if not (title and price):
            return None
        extract = ProductExtract(
            url=url, canonical_url=canonical_url, seller_domain=seller_domain, name=title
        )
    if not extract.price_cents and price:
        extract.price_cents = price
        extract.currency = (meta("product:price:currency", "og:price:currency") or extract.currency).upper()
    extract.name = extract.name or title or ""
    extract.image_url = extract.image_url or meta("og:image")
    extract.brand = extract.brand or meta("product:brand", "og:brand")
    if "meta" not in extract.extracted_by:
        extract.extracted_by.append("meta")
    return extract


def canonical_link(soup: BeautifulSoup) -> str | None:
    tag = soup.find("link", rel="canonical")
    return attr_str(tag, "href") if tag else None
