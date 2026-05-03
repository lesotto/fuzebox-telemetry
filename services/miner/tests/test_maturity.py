"""Twin Maturity Score tests."""

from __future__ import annotations

from services.miner.app.maturity import (
    MaturityInputs,
    compute,
    js_divergence,
    variant_stability,
)


def test_perfect_score() -> None:
    score = compute(
        MaturityInputs(
            coverage=1.0,
            cosign_rate=1.0,
            variant_stability=1.0,
            outcome_signal=1.0,
            n_cases=1000,
        )
    )
    assert score.score == 100.0
    assert score.band == "production_ready"


def test_thin_pilot_lands_in_too_thin_band() -> None:
    score = compute(
        MaturityInputs(
            coverage=0.5,
            cosign_rate=0.1,
            variant_stability=0.4,
            outcome_signal=0.2,
            n_cases=20,
        )
    )
    # 0.20*(0.5+0.1+0.4+0.2) + 0.20*0.04 = 0.248 → 24.8
    assert score.score < 40.0
    assert score.band == "too_thin"


def test_population_capped_at_500_cases() -> None:
    a = compute(
        MaturityInputs(
            coverage=1.0,
            cosign_rate=1.0,
            variant_stability=1.0,
            outcome_signal=1.0,
            n_cases=500,
        )
    )
    b = compute(
        MaturityInputs(
            coverage=1.0,
            cosign_rate=1.0,
            variant_stability=1.0,
            outcome_signal=1.0,
            n_cases=10_000,
        )
    )
    assert a.score == b.score == 100.0


def test_js_divergence_zero_for_same_distribution() -> None:
    a = {("x",): 5, ("y",): 5}
    assert js_divergence(a, a) == 0.0


def test_js_divergence_positive_for_different_distributions() -> None:
    a = {("x",): 10}
    b = {("y",): 10}
    assert js_divergence(a, b) > 0.5


def test_variant_stability_reflects_drift() -> None:
    # Identical → 1.0
    same = variant_stability([("a",), ("b",)], [("a",), ("b",)])
    assert same == 1.0
    # Totally different → < 1.0
    diff = variant_stability([("a",)], [("b",)])
    assert diff < same


def test_operational_band() -> None:
    score = compute(
        MaturityInputs(
            coverage=0.6,
            cosign_rate=0.5,
            variant_stability=0.5,
            outcome_signal=0.5,
            n_cases=300,
        )
    )
    assert 40.0 <= score.score < 60.0
    assert score.band == "operational"
