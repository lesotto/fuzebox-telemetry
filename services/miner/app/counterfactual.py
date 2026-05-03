"""Four-tier counterfactual simulator.

For each PEL row, return (outcome_usd, confidence, method):

  Tier 1 — holdout assignment exists                       confidence 1.00
  Tier 2 — process-twin replay (>=5 similar cases)         confidence 0.85
  Tier 3 — variant average (>=3 same-variant cases)        confidence 0.55
  Tier 4 — synthetic from trailing 7-day signal            confidence 0.30
  Otherwise — None, 0.00, "insufficient_data"

A row whose method comes back below 0.30 confidence MUST NOT receive a
`lift_usd`. The cosign state machine (Sprint 2) already enforces this gate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class HistoricalRow:
    """Lightweight view of a PEL row that the simulator needs."""

    case_id: str
    skill: str
    variant: tuple[str, ...]
    actual_outcome_usd: Decimal | None
    holdout: bool
    created_at: datetime
    activities: frozenset[str]


@dataclass(frozen=True)
class CounterfactualResult:
    outcome_usd: Decimal | None
    confidence: Decimal
    method: str


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _holdout(row: HistoricalRow, population: Sequence[HistoricalRow]) -> Decimal | None:
    if not row.holdout:
        return None
    same_skill_holdouts = [
        r for r in population
        if r.holdout and r.skill == row.skill and r.actual_outcome_usd is not None
    ]
    if not same_skill_holdouts:
        return None
    total = sum((r.actual_outcome_usd for r in same_skill_holdouts), start=Decimal("0"))
    return total / Decimal(len(same_skill_holdouts))


def _twin_replay(
    row: HistoricalRow, population: Sequence[HistoricalRow], decision_activity: str
) -> Decimal | None:
    similar = [
        r
        for r in population
        if r.skill == row.skill
        and r.case_id != row.case_id
        and decision_activity not in r.activities
        and r.actual_outcome_usd is not None
    ]
    if len(similar) < 5:
        return None
    weights = [Decimal(str(_jaccard(row.activities, r.activities))) for r in similar]
    total_weight = sum(weights, start=Decimal("0"))
    if total_weight == 0:
        return None
    weighted = sum(
        ((r.actual_outcome_usd or Decimal("0")) * w for r, w in zip(similar, weights, strict=True)),
        start=Decimal("0"),
    )
    return weighted / total_weight


def _variant_average(
    row: HistoricalRow, population: Sequence[HistoricalRow]
) -> Decimal | None:
    same_variant = [
        r
        for r in population
        if r.skill == row.skill
        and r.case_id != row.case_id
        and r.variant == row.variant
        and r.actual_outcome_usd is not None
    ]
    if len(same_variant) < 3:
        return None
    total = sum((r.actual_outcome_usd for r in same_variant), start=Decimal("0"))
    return total / Decimal(len(same_variant))


def _trailing_7d(
    row: HistoricalRow, population: Sequence[HistoricalRow]
) -> Decimal | None:
    cutoff = row.created_at - timedelta(days=7)
    pool = [
        r
        for r in population
        if r.skill == row.skill
        and r.created_at >= cutoff
        and r.actual_outcome_usd is not None
    ]
    if len(pool) < 1:
        return None
    total = sum((r.actual_outcome_usd for r in pool), start=Decimal("0"))
    return total / Decimal(len(pool))


def estimate_counterfactual(
    row: HistoricalRow,
    population: Sequence[HistoricalRow],
    *,
    decision_activity: str = "agent.decision",
) -> CounterfactualResult:
    holdout = _holdout(row, population)
    if holdout is not None:
        return CounterfactualResult(holdout, Decimal("1.00"), "holdout")

    twin = _twin_replay(row, population, decision_activity)
    if twin is not None:
        return CounterfactualResult(twin, Decimal("0.85"), "process_twin_replay")

    variant = _variant_average(row, population)
    if variant is not None:
        return CounterfactualResult(variant, Decimal("0.55"), "variant_average")

    synthetic = _trailing_7d(row, population)
    if synthetic is not None:
        return CounterfactualResult(synthetic, Decimal("0.30"), "synthetic")

    return CounterfactualResult(None, Decimal("0.00"), "insufficient_data")


__all__ = [
    "CounterfactualResult",
    "HistoricalRow",
    "estimate_counterfactual",
]
