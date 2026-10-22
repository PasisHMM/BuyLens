"""Price Check: total cost and comparison with the market average of comparable listings."""

from statistics import mean

from app.pipeline.models import Candidate, Match, PriceCheck

MIN_COMPARABLES = 3


def shipping_for(candidate: Candidate) -> int | None:
    """Shipping from the page; else the seller's *verified* rule; else unknown (never assumed free)."""
    if candidate.extract.shipping_cents is not None:
        return candidate.extract.shipping_cents
    policy = candidate.seller.shipping_policy
    if not policy.verified:
        return None
    if policy.free_over_cents is not None and candidate.extract.price_cents >= policy.free_over_cents:
        return 0
    return policy.flat_cents


def market_average(candidates: list[Candidate], currency: str) -> tuple[int | None, int]:
    """Trimmed mean of listing prices (shipping excluded) over same-product, same-currency listings."""
    prices = sorted(
        c.extract.price_cents
        for c in candidates
        if c.match in (Match.EXACT, Match.LIKELY) and c.extract.currency == currency
    )
    if len(prices) < MIN_COMPARABLES:
        return None, len(prices)
    trimmed = prices[1:-1] if len(prices) >= 5 else prices
    return round(mean(trimmed)), len(prices)


def evaluate_prices(candidates: list[Candidate]) -> dict[int, PriceCheck]:
    """PriceCheck per candidate, keyed by position in `candidates`."""
    if not candidates:
        return {}
    currency = candidates[0].extract.currency
    avg, count = market_average(candidates, currency)
    checks: dict[int, PriceCheck] = {}
    for i, c in enumerate(candidates):
        listing = c.extract.price_cents
        shipping = shipping_for(c)
        delta = listing - avg if avg is not None and c.extract.currency == currency else None
        checks[i] = PriceCheck(
            currency=c.extract.currency,
            listing_cents=listing,
            shipping_cents=shipping,
            total_cents=listing + (shipping or 0),
            total_is_estimate=shipping is None,
            market_avg_cents=avg,
            delta_cents=delta,
            delta_pct=round(delta / avg * 100, 1) if delta is not None and avg else None,
            comparable_count=count,
        )
    return checks
