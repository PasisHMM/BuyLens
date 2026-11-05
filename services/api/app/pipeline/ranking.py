"""Result groups and order. Fit comes first; a mismatch is never presented as an alternative.

MATCH and UNCERTAIN options are visible. MISMATCH options stay in storage but leave the visible list.
Within a group the lowest total comes first. The budget joins this order in Phase 4 (§2.3).
"""

from typing import Literal

from app.pipeline.models import FitOutcome, RankedOption, SellerRisk

ResultGroup = Literal["matches", "uncertain", "hidden"]

_GROUP: dict[FitOutcome, ResultGroup] = {
    FitOutcome.MATCH: "matches",
    FitOutcome.UNCERTAIN: "uncertain",
    FitOutcome.MISMATCH: "hidden",
}
_FIT_ORDER = {FitOutcome.MATCH: 0, FitOutcome.UNCERTAIN: 1, FitOutcome.MISMATCH: 2}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, None: 3}


def result_group(outcome: FitOutcome) -> ResultGroup:
    return _GROUP[outcome]


def rank(options: list[RankedOption]) -> list[RankedOption]:
    ordered = sorted(
        options, key=lambda o: (_FIT_ORDER[o.fit.outcome], o.price.total_cents, _RISK_ORDER[o.risk.level])
    )
    return [o.model_copy(update={"rank": i}) for i, o in enumerate(ordered, start=1)]


def selected_size(options: list[RankedOption]) -> str | None:
    """The size of the first visible option. A hidden option suggests no size."""
    for option in options:
        if option.fit.outcome is not FitOutcome.MISMATCH and option.fit.size_label:
            return option.fit.size_label
    return None


def seller_summary(risk: SellerRisk) -> str:
    parts = ["Official store"] if risk.is_official else []
    policy = risk.return_policy
    parts.append(policy.title or "Return policy" if policy.verified else "Return policy not verified")
    return " · ".join(parts)
