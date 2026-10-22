"""Seller Risk: curated seller data + review aggregates + an LLM summary of review text."""

from typing import Literal

from pydantic import BaseModel

from app.llm import LLM, LLMError
from app.pipeline.models import Candidate, SellerRisk

MIN_REVIEWS_FOR_SUMMARY = 3
MIN_REVIEWS_FOR_RATING_SIGNAL = 20

SYSTEM = """You summarize customer reviews of one clothing product for a shopping assistant.
Use only what the reviews say. Do not invent themes. Each theme is a short phrase (max 8 words).
fit_signal: "runs_small" or "runs_large" only if several reviews agree; "true_to_size" if several say so;
otherwise "unknown". red_flags: quality or seller problems mentioned more than once (e.g. "seams split")."""


class ReviewSummary(BaseModel):
    themes: list[str]
    fit_signal: Literal["runs_small", "true_to_size", "runs_large", "unknown"]
    red_flags: list[str]


async def summarize_reviews(llm: LLM, texts: list[str]) -> ReviewSummary | None:
    if len(texts) < MIN_REVIEWS_FOR_SUMMARY:
        return None
    body = "\n".join(f"- {t[:600]}" for t in texts[:30])
    try:
        return await llm.structured(
            tier="fast",
            system=SYSTEM,
            prompt=f"<reviews>\n{body}\n</reviews>",
            schema=ReviewSummary,
            max_tokens=512,
        )
    except LLMError:
        return None


def evaluate_seller(candidate: Candidate, summary: ReviewSummary | None) -> SellerRisk:
    seller, extract = candidate.seller, candidate.extract
    policy = seller.return_policy
    rating, count = extract.review_rating, extract.review_count
    poor_reviews = rating is not None and rating < 3.5 and (count or 0) >= MIN_REVIEWS_FOR_RATING_SIGNAL
    red_flags = summary.red_flags if summary else []

    level: Literal["low", "medium", "high"]
    if (seller.trust_rating is not None and seller.trust_rating < 3.0) or poor_reviews or len(red_flags) >= 2:
        level = "high"
    elif (
        (candidate.is_official or (seller.trust_rating or 0) >= 4.3)
        and policy.verified
        and (policy.window_days or 0) >= 14
        and not red_flags
    ):
        level = "low"
    else:
        level = "medium"  # includes: return policy not verified yet

    highlights = (summary.themes[:3] if summary else []) + red_flags[:2]
    return SellerRisk(
        seller_name=seller.name,
        is_official=candidate.is_official,
        trust_rating=seller.trust_rating,
        level=level,
        review_rating=rating,
        review_count=count,
        return_policy=policy,
        review_highlights=highlights,
        fit_signal=summary.fit_signal if summary else "unknown",
    )
