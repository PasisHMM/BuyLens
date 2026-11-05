"""Price Check: the actual price, shipping and total of each listing."""

from app.pipeline.models import Candidate, PriceCheck


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


def evaluate_prices(candidates: list[Candidate]) -> dict[int, PriceCheck]:
    """PriceCheck per candidate, keyed by position in `candidates`."""
    checks: dict[int, PriceCheck] = {}
    for i, c in enumerate(candidates):
        listing = c.extract.price_cents
        shipping = shipping_for(c)
        checks[i] = PriceCheck(
            currency=c.extract.currency,
            listing_cents=listing,
            shipping_cents=shipping,
            total_cents=listing + (shipping or 0),
            total_is_estimate=shipping is None,
        )
    return checks
