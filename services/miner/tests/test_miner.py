"""Miner: variant recovery + transition stats + perf."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from services.miner.app.miner import Event, mine, synth_log


def test_recovers_planted_variants() -> None:
    log = synth_log(
        n_cases=500,
        variants={
            ("intake", "extract", "decision", "close"): 0.7,
            ("intake", "extract", "review", "close"): 0.2,
            ("intake", "decision", "close"): 0.1,
        },
    )
    artifact = mine(log, tenant="acme", skill="claims_triage")
    assert artifact.n_cases == 500
    sequences = {v.sequence for v in artifact.variants}
    assert ("intake", "extract", "decision", "close") in sequences
    assert ("intake", "extract", "review", "close") in sequences
    assert ("intake", "decision", "close") in sequences
    # The dominant variant should be largest.
    assert artifact.variants[0].sequence == ("intake", "extract", "decision", "close")


def test_transition_stats_compute_waits() -> None:
    base = datetime(2026, 5, 3, tzinfo=UTC)
    log = [
        Event(case_id="c1", activity="a", timestamp=base),
        Event(case_id="c1", activity="b", timestamp=base + timedelta(seconds=10)),
        Event(case_id="c2", activity="a", timestamp=base),
        Event(case_id="c2", activity="b", timestamp=base + timedelta(seconds=20)),
    ]
    artifact = mine(log, tenant="t", skill="s")
    a_to_b = next(t for t in artifact.transitions if t.src == "a" and t.dst == "b")
    assert a_to_b.count == 2
    assert a_to_b.mean_wait_s == 15.0


def test_mine_under_one_second_for_500_cases() -> None:
    log = synth_log(
        n_cases=500,
        variants={
            ("intake", "extract", "decision", "close"): 0.7,
            ("intake", "extract", "review", "close"): 0.2,
            ("intake", "decision", "close"): 0.1,
        },
    )
    started = time.perf_counter()
    mine(log, tenant="acme", skill="claims_triage")
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, f"miner took {elapsed:.2f}s, expected <1s for 500 cases"


def test_subsamples_above_threshold() -> None:
    # Threshold is on event count, not case count.
    log = synth_log(n_cases=1100, variants={("a", "b"): 1.0})  # 2200 events
    artifact = mine(log, tenant="t", skill="s", subsample_threshold=5000)
    assert artifact.subsampled is False
    artifact = mine(log, tenant="t", skill="s", subsample_threshold=500)
    assert artifact.subsampled is True


def test_to_json_serializable() -> None:
    import json

    log = synth_log(n_cases=10, variants={("a", "b"): 1.0})
    artifact = mine(log, tenant="t", skill="s")
    blob = json.dumps(artifact.to_json(), default=str)
    assert "variants" in blob
