"""Four-tier counterfactual simulator tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from services.miner.app.counterfactual import HistoricalRow, estimate_counterfactual


def _row(
    case_id: str,
    *,
    skill: str = "claims_triage",
    variant: tuple[str, ...] = ("intake", "agent.decision", "close"),
    actual: Decimal | None = Decimal("50"),
    holdout: bool = False,
    activities: frozenset[str] | None = None,
    ts: datetime | None = None,
) -> HistoricalRow:
    return HistoricalRow(
        case_id=case_id,
        skill=skill,
        variant=variant,
        actual_outcome_usd=actual,
        holdout=holdout,
        created_at=ts or datetime(2026, 5, 3, tzinfo=UTC),
        activities=activities or frozenset(variant),
    )


def test_holdout_tier() -> None:
    target = _row("t", holdout=True)
    pop = [_row(f"h{i}", holdout=True, actual=Decimal("40")) for i in range(3)]
    r = estimate_counterfactual(target, pop)
    assert r.method == "holdout"
    assert r.confidence == Decimal("1.00")
    assert r.outcome_usd == Decimal("40")


def test_process_twin_replay_tier() -> None:
    target = _row("t", activities=frozenset({"intake", "agent.decision", "close"}))
    pop = [
        _row(
            f"p{i}",
            variant=("intake", "human", "close"),
            actual=Decimal(str(40 + i)),
            activities=frozenset({"intake", "human", "close"}),
        )
        for i in range(7)
    ]
    r = estimate_counterfactual(target, pop)
    assert r.method == "process_twin_replay"
    assert r.confidence == Decimal("0.85")
    assert r.outcome_usd is not None


def test_variant_average_tier() -> None:
    target = _row("t")
    # 4 same-variant rows (no agent.decision-free path with >=5 → tier 2 fails)
    pop = [_row(f"v{i}", actual=Decimal("60")) for i in range(4)]
    r = estimate_counterfactual(target, pop)
    assert r.method == "variant_average"
    assert r.outcome_usd == Decimal("60")


def test_synthetic_trailing_7d_tier() -> None:
    target = _row("t", ts=datetime(2026, 5, 10, tzinfo=UTC))
    # No same-variant rows, but trailing 7 days has some signal.
    pop = [
        _row(
            f"s{i}",
            variant=("totally", "different"),
            activities=frozenset({"totally", "different"}),
            actual=Decimal("25"),
            ts=datetime(2026, 5, 8, tzinfo=UTC),
        )
        for i in range(2)
    ]
    r = estimate_counterfactual(target, pop)
    assert r.method == "synthetic"
    assert r.confidence == Decimal("0.30")
    assert r.outcome_usd == Decimal("25")


def test_insufficient_data() -> None:
    target = _row(
        "t",
        ts=datetime(2027, 1, 1, tzinfo=UTC),
        variant=("unique", "path"),
        activities=frozenset({"unique", "path"}),
    )
    r = estimate_counterfactual(target, [])
    assert r.method == "insufficient_data"
    assert r.outcome_usd is None
    assert r.confidence == Decimal("0")


def test_holdout_takes_precedence() -> None:
    target = _row("t", holdout=True)
    pop = [_row(f"h{i}", holdout=True, actual=Decimal("33")) for i in range(3)]
    pop.extend(_row(f"x{i}", actual=Decimal("99")) for i in range(20))
    r = estimate_counterfactual(target, pop)
    assert r.method == "holdout"
    assert r.outcome_usd == Decimal("33")
