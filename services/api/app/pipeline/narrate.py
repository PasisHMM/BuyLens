"""Verdict copy. Rules decide; this module only explains.

`template_copy()` always works and is used whenever the LLM is unavailable or its copy fails
`check_copy()`. The "Why not BUY / SKIP?" lines are always deterministic.
"""

import json
import re
from typing import Any

from pydantic import BaseModel

from app.llm import LLM, LLMError
from app.pipeline.models import (
    DIMENSION_NOUN,
    Decision,
    FitMatch,
    Narrative,
    ProductExtract,
    RankedOption,
    Verdict,
)

CM_PER_IN = 2.54
BANNED = re.compile(r"guarantee|perfect fit|will (definitely )?fit|100% fit", re.IGNORECASE)
MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{2})?)")

SYSTEM = """You write verdict copy for Buy Lens, a shopping second-opinion tool.
Rules:
- The verdict and reason codes in <facts> are FINAL. Explain them; never change, soften, or contradict them.
- Use only facts in <facts>. Never invent measurements, prices, policies, or review claims.
- If a measurement is missing, name it plainly. Never imply a guaranteed fit.
- Tone: calm, direct, friendly. No exclamation marks.
- headline: at most 9 words. explanation: at most 2 sentences.
- option_summaries: one short phrase per option, in rank order, saying why it ranks there."""


class LLMCopy(BaseModel):
    headline: str
    explanation: str
    option_summaries: list[str]


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _policy_unverified(option: RankedOption) -> bool:
    return not option.risk.return_policy.verified


def _reason_sentence(code: str, option: RankedOption, decision: Decision) -> str:
    fit, price = option.fit, option.price
    if code == "FIT_MISMATCH":
        bad = [r for r in fit.rows if r.match not in (FitMatch.OK, FitMatch.MISSING)]
        return " ".join(f"It's likely {r.match.value} at the {r.dimension}." for r in bad[:2])
    if code == "FIT_DATA_MISSING":
        if not fit.rows or all(r.match is FitMatch.MISSING for r in fit.rows):
            return "The seller doesn't publish measurements we can compare with yours."
        dims = _join([DIMENSION_NOUN.get(d, d) for d in decision.missing_dimensions])
        article = "an" if dims[:1] in "aeiou" else "a"
        return (
            f"The seller doesn't list {article} {dims} measurement, "
            "so we won't call it a sure fit without one."
        )
    if code == "FIT_UNCERTAIN":
        return "Size data is incomplete or reviews disagree on the fit."
    if code in ("OVERPRICED", "ABOVE_MARKET"):
        return f"It's {price.delta_pct:.0f}% above the market average."
    if code == "SELLER_HIGH_RISK":
        return "The seller's reviews or track record raise concerns."
    if code == "RETURN_RISK":
        if _policy_unverified(option):
            return "We haven't verified this store's return policy yet."
        return "Returns aren't free here."
    return ""


def _positives(option: RankedOption) -> list[str]:
    good = [r.dimension for r in option.fit.rows if r.match is FitMatch.OK]
    out = []
    if good:
        out.append(f"the {_join(good)} {'looks' if len(good) == 1 else 'look'} right")
    if option.risk.level == "low":
        out.append("the official store is low risk" if option.risk.is_official else "the seller is low risk")
    if option.price.delta_pct is not None and option.price.delta_pct <= 0:
        out.append("the price is below the market average")
    return out


def _headline(option: RankedOption, decision: Decision) -> str:
    reasons, price = decision.reasons, option.price
    good_price = price.delta_pct is not None and price.delta_pct <= 0
    if decision.verdict is Verdict.BUY:
        return "Fits your numbers at a fair price."
    if decision.verdict is Verdict.SKIP:
        if "FIT_MISMATCH" in reasons:
            bad = next(r for r in option.fit.rows if r.match not in (FitMatch.OK, FitMatch.MISSING))
            return f"Likely {bad.match.value} at the {bad.dimension}. Skip this one."
        if "OVERPRICED" in reasons:
            return "Costs well above the usual price."
        return "Risky seller. Skip this one."
    prefix = "Good price. " if good_price else ""
    if "FIT_DATA_MISSING" in reasons and decision.missing_dimensions and option.fit.rows:
        if len(decision.missing_dimensions) < len(option.fit.rows):
            return f"{prefix}Check the {_join(decision.missing_dimensions)} before you buy."
        return f"{prefix}Check the size chart before you buy."
    if "FIT_DATA_MISSING" in reasons or "FIT_UNCERTAIN" in reasons:
        return f"{prefix}Double-check the size before you buy."
    if "ABOVE_MARKET" in reasons:
        return "Looks right, but costs more than usual."
    return f"{prefix}Looks right. Check the return policy."


def _option_summary(option: RankedOption, options: list[RankedOption]) -> str:
    cheapest = min(o.price.total_cents for o in options)
    parts = []
    if option.rank == 1:
        parts.append("Best overall value")
    if option.price.total_cents == cheapest and len(options) > 1:
        parts.append("lowest total cost")
    if option.risk.is_official:
        parts.append("official brand store")
    if option.risk.return_policy.verified and option.risk.return_policy.free:
        parts.append("free returns")
    if option.fit.confidence == "high":
        parts.append("full size data")
    text = ", ".join(parts) or "Also available"
    return text[:1].upper() + text[1:] + "."


def why_not(option: RankedOption, decision: Decision) -> tuple[str | None, str | None]:
    v, reasons = decision.verdict, decision.reasons
    not_buy = None
    if v is not Verdict.BUY and reasons:
        not_buy = _reason_sentence(reasons[0], option, decision)
    not_skip = None
    if v is not Verdict.SKIP:
        passing = []
        if option.price.delta_pct is None or option.price.delta_pct <= 5:
            passing.append(
                "the price is competitive"
                if option.price.delta_pct is not None
                else "nothing in the price stands out"
            )
        if option.risk.return_policy.verified and option.risk.return_policy.free:
            passing.append("returns are free")
        if not any(r.match not in (FitMatch.OK, FitMatch.MISSING) for r in option.fit.rows):
            passing.append("no measurement rules it out")
        if passing:
            text = _join(passing)
            not_skip = text[:1].upper() + text[1:] + "."
    return not_buy, not_skip


def template_copy(options: list[RankedOption], decision: Decision) -> Narrative:
    best = options[0]
    positives = _positives(best)
    negatives = [s for code in decision.reasons if (s := _reason_sentence(code, best, decision))]
    explanation = ""
    if positives:
        text = _join(positives)
        explanation = text[:1].upper() + text[1:] + "."
    if negatives:
        explanation = (
            f"{explanation} But {negatives[0][:1].lower()}{negatives[0][1:]}" if explanation else negatives[0]
        )
        explanation += "".join(f" {s}" for s in negatives[1:2])
    not_buy, not_skip = why_not(best, decision)
    return Narrative(
        headline=_headline(best, decision),
        explanation=explanation.strip() or "Here's what we found.",
        why_not_buy=not_buy,
        why_not_skip=not_skip,
        option_summaries=[_option_summary(o, options) for o in options],
        written_by="template",
    )


def facts(product: ProductExtract, options: list[RankedOption], decision: Decision,
          memory_notes: list[str]) -> dict[str, Any]:  # fmt: skip
    """What the LLM may use. Fit is sent as outcomes and room, never the user's raw measurements."""
    return {
        "product": {"name": product.name, "brand": product.brand, "attributes": product.attributes},
        "verdict": decision.verdict.value,
        "reason_codes": decision.reasons,
        "missing_measurements": decision.missing_dimensions,
        "options": [
            {
                "rank": o.rank,
                "seller": o.risk.seller_name,
                "official_store": o.risk.is_official,
                "total": _money(o.price.total_cents),
                "shipping": "unknown" if o.price.shipping_cents is None else _money(o.price.shipping_cents),
                "market_average": _money(o.price.market_avg_cents) if o.price.market_avg_cents else None,
                "vs_market_pct": o.price.delta_pct,
                "fit_confidence": o.fit.confidence,
                "fit": [
                    {
                        "dimension": r.dimension,
                        "result": r.match.value,
                        "room_in": round(r.room_cm / CM_PER_IN, 1) if r.room_cm is not None else None,
                    }
                    for r in o.fit.rows
                ],
                "seller_risk": o.risk.level,
                "returns": o.risk.return_policy.title if o.risk.return_policy.verified else "not verified",
                "review_highlights": o.risk.review_highlights,
            }
            for o in options
        ],
        "past_feedback": memory_notes,
    }


def check_copy(copy: LLMCopy, options: list[RankedOption], decision: Decision) -> bool:
    text = f"{copy.headline} {copy.explanation}"
    if len(copy.headline.split()) > 12 or len(copy.explanation) > 400 or "!" in text:
        return False
    if BANNED.search(text) or any(BANNED.search(s) for s in copy.option_summaries):
        return False
    if len(copy.option_summaries) != len(options):
        return False
    lower = text.lower()
    if decision.verdict is not Verdict.SKIP and re.search(r"\bskip (it|this)\b|\bdon'?t buy\b", lower):
        return False
    if decision.verdict is not Verdict.BUY and re.search(r"\bbuy it\b|\bgo for it\b|\bsafe bet\b", lower):
        return False
    if (
        "FIT_DATA_MISSING" in decision.reasons
        and decision.missing_dimensions
        and not any(DIMENSION_NOUN.get(d, d) in lower for d in decision.missing_dimensions)
    ):
        return False
    # Every dollar amount must be a known total, listing price, or market average.
    known = {o.price.total_cents for o in options} | {o.price.listing_cents for o in options}
    known |= {o.price.market_avg_cents for o in options if o.price.market_avg_cents}
    known |= {abs(o.price.delta_cents) for o in options if o.price.delta_cents}
    for amount in MONEY.findall(" ".join([text, *copy.option_summaries])):
        cents = round(float(amount.replace(",", "")) * 100)
        if cents not in known:
            return False
    return True


async def write_copy(llm: LLM | None, product: ProductExtract, options: list[RankedOption],
                     decision: Decision, memory_notes: list[str] | None = None) -> Narrative:  # fmt: skip
    fallback = template_copy(options, decision)
    if llm is None:
        return fallback
    prompt = (
        f"<facts>\n{json.dumps(facts(product, options, decision, memory_notes or []), indent=1)}\n</facts>\n"
        f"<draft>\n{fallback.model_dump_json(include={'headline', 'explanation'})}\n</draft>\n"
        "Improve the draft wording if you can, keeping every claim."
    )
    for _ in range(2):  # one retry, then the template
        try:
            copy = await llm.structured(
                tier="smart", system=SYSTEM, prompt=prompt, schema=LLMCopy, max_tokens=800
            )
        except LLMError:
            return fallback
        if check_copy(copy, options, decision):
            return fallback.model_copy(
                update={
                    "headline": copy.headline.strip(),
                    "explanation": copy.explanation.strip(),
                    "option_summaries": [s.strip() for s in copy.option_summaries],
                    "written_by": "llm",
                }
            )
    return fallback
