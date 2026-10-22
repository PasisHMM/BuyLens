"""Ranking and the verdict rules. The verdict is decided here, never by the LLM."""

from app.pipeline.models import (
    Decision,
    DecisionMemory,
    FitCheck,
    FitMatch,
    PriceCheck,
    RankedOption,
    SellerRisk,
    Verdict,
)

OVERPRICED_PCT = 25.0
ABOVE_MARKET_PCT = 5.0
MISFIT = (FitMatch.TIGHT, FitMatch.LOOSE, FitMatch.SHORT, FitMatch.LONG)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def score(price: PriceCheck, fit: FitCheck, risk: SellerRisk, dm: DecisionMemory) -> float:
    """Overall value in 0..1 ("Ranked by overall value, not just lowest price")."""
    w_price = 0.35 + 0.2 * (dm.price_sensitivity - 0.5)
    w_fit = 0.40 + 0.2 * (dm.fit_strictness - 0.5)
    w_risk = 0.25 + 0.2 * (dm.risk_aversion - 0.5)

    price_s = _clamp(0.5 - (price.delta_pct or 0.0) / 40)  # 20% under market → 1.0
    measured = [r for r in fit.rows if r.match is not FitMatch.MISSING]
    ok_ratio = sum(r.match is FitMatch.OK for r in measured) / len(measured) if measured else 0.5
    fit_s = {"high": 1.0, "medium": 0.7, "limited": 0.5}[fit.confidence] * ok_ratio
    policy = risk.return_policy
    returns = 1.0 if policy.verified and policy.free else 0.8 if policy.verified else 0.7
    risk_s = {"low": 1.0, "medium": 0.6, "high": 0.1}[risk.level] * returns
    return round((w_price * price_s + w_fit * fit_s + w_risk * risk_s) / (w_price + w_fit + w_risk), 4)


def decide(option: RankedOption, dm: DecisionMemory | None = None) -> Decision:
    fit, price, risk = option.fit, option.price, option.risk
    missing = [r.dimension for r in fit.rows if r.match is FitMatch.MISSING]

    hard: list[str] = []
    if any(r.match in MISFIT for r in fit.rows):
        hard.append("FIT_MISMATCH")
    if risk.level == "high":
        hard.append("SELLER_HIGH_RISK")
    if price.delta_pct is not None and price.delta_pct > OVERPRICED_PCT:
        hard.append("OVERPRICED")
    if hard:
        return Decision(verdict=Verdict.SKIP, reasons=hard, missing_dimensions=missing)

    soft: list[str] = []
    if missing or not fit.rows:
        soft.append("FIT_DATA_MISSING")
    elif fit.confidence != "high":
        soft.append("FIT_UNCERTAIN")
    if price.delta_pct is not None and price.delta_pct > ABOVE_MARKET_PCT:
        soft.append("ABOVE_MARKET")
    if risk.level == "medium" or not (risk.return_policy.verified and risk.return_policy.free):
        soft.append("RETURN_RISK")
    if dm and dm.fit_strictness > 0.7 and fit.confidence != "high" and "FIT_UNCERTAIN" not in soft:
        soft.append("FIT_UNCERTAIN")
    return Decision(
        verdict=Verdict.CONSIDER if soft else Verdict.BUY, reasons=soft, missing_dimensions=missing
    )


def rank(options: list[RankedOption], limit: int = 3) -> list[RankedOption]:
    ordered = sorted(options, key=lambda o: (-o.score, o.price.total_cents))
    return [o.model_copy(update={"rank": i}) for i, o in enumerate(ordered[:limit], start=1)]
