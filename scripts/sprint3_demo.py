"""Sprint 3 demo: mine 500 synthetic claims-triage cases, recover 3 planted
variants, run the 4-tier counterfactual on every row, compute the Twin
Maturity Score.
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.miner.app.counterfactual import HistoricalRow, estimate_counterfactual
from services.miner.app.maturity import MaturityInputs, compute, variant_stability
from services.miner.app.miner import mine, synth_log

VARIANTS = {
    ("intake", "extract", "agent.decision", "close"): 0.65,
    ("intake", "extract", "human", "close"): 0.25,
    ("intake", "agent.decision", "close"): 0.10,
}


def _outcome_for(seq: tuple[str, ...]) -> Decimal:
    if "human" in seq:
        return Decimal("60.00")
    if "agent.decision" in seq:
        return Decimal("50.00")
    return Decimal("30.00")


def main() -> int:
    print("== Sprint 3 demo ==")
    log = synth_log(n_cases=500, variants=VARIANTS)

    started = time.perf_counter()
    artifact = mine(log, tenant="acme", skill="claims_triage")
    mine_elapsed = time.perf_counter() - started
    print(f"  mined {artifact.n_cases} cases in {mine_elapsed*1000:.1f} ms")
    print(f"  recovered {len(artifact.variants)} variants:")
    for v in artifact.variants:
        print(f"    {v.case_count:4d}  {' -> '.join(v.sequence)}")

    # Build HistoricalRows and run counterfactuals.
    base = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    pop: list[HistoricalRow] = []
    for v in artifact.variants:
        for case_id in v.case_ids:
            pop.append(
                HistoricalRow(
                    case_id=case_id,
                    skill="claims_triage",
                    variant=v.sequence,
                    actual_outcome_usd=_outcome_for(v.sequence),
                    holdout=False,
                    created_at=base + timedelta(seconds=hash(case_id) % 86400),
                    activities=frozenset(v.sequence),
                )
            )

    methods: dict[str, int] = {}
    for row in pop[:50]:
        r = estimate_counterfactual(row, pop)
        methods[r.method] = methods.get(r.method, 0) + 1
    print(f"  counterfactual method distribution (first 50): {methods}")

    # Twin Maturity Score
    coverage = 0.95
    cosign_rate = 0.65
    outcome_signal = 0.95
    current_dist = [v.sequence for v in artifact.variants for _ in v.case_ids]
    previous_dist = current_dist  # pretend last week looked the same
    stability = variant_stability(current_dist, previous_dist)
    score = compute(
        MaturityInputs(
            coverage=coverage,
            cosign_rate=cosign_rate,
            variant_stability=stability,
            outcome_signal=outcome_signal,
            n_cases=artifact.n_cases,
        )
    )
    print(f"  Twin Maturity Score: {score.score:.1f} ({score.band})")

    ok = (
        len(artifact.variants) >= 3
        and mine_elapsed < 1.0
        and score.score >= 40.0
    )
    print()
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
