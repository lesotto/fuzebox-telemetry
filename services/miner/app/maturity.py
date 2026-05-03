"""Twin Maturity Score.

Five components, each weighted at 0.20:

  - coverage          % of agent calls captured as spans
  - cosign_rate       % of closed rows at T3+
  - variant_stability 1 - JS divergence vs. last week's distribution
  - outcome_signal    % of rows with actual_outcome_usd
  - population        min(1.0, n_cases / 500)

Returns 0..100. Bands:
  <40   too thin
  40-60 operational
  60-80 stable
  80+   production-ready
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class MaturityInputs:
    coverage: float
    cosign_rate: float
    variant_stability: float
    outcome_signal: float
    n_cases: int


@dataclass(frozen=True)
class MaturityScore:
    score: float
    band: str
    components: dict[str, float]


_WEIGHTS = {
    "coverage": 0.20,
    "cosign_rate": 0.20,
    "variant_stability": 0.20,
    "outcome_signal": 0.20,
    "population": 0.20,
}


def _band(score: float) -> str:
    if score < 40:
        return "too_thin"
    if score < 60:
        return "operational"
    if score < 80:
        return "stable"
    return "production_ready"


def js_divergence(a: dict[tuple[str, ...], int], b: dict[tuple[str, ...], int]) -> float:
    """Jensen-Shannon divergence between two empirical distributions over variants.

    Returns a value in [0, 1] (using log base 2). Identical distributions → 0.
    """

    keys = set(a) | set(b)
    if not keys:
        return 0.0
    sa = sum(a.values()) or 1
    sb = sum(b.values()) or 1
    pa = {k: a.get(k, 0) / sa for k in keys}
    pb = {k: b.get(k, 0) / sb for k in keys}
    m = {k: 0.5 * (pa[k] + pb[k]) for k in keys}

    def _kl(p: dict[tuple[str, ...], float], q: dict[tuple[str, ...], float]) -> float:
        total = 0.0
        for k in p:
            if p[k] > 0 and q[k] > 0:
                total += p[k] * math.log2(p[k] / q[k])
        return total

    return 0.5 * _kl(pa, m) + 0.5 * _kl(pb, m)


def variant_stability(
    current: Iterable[tuple[str, ...]], previous: Iterable[tuple[str, ...]]
) -> float:
    a = Counter(current)
    b = Counter(previous)
    if not a and not b:
        return 1.0
    return max(0.0, 1.0 - js_divergence(dict(a), dict(b)))


def compute(inputs: MaturityInputs) -> MaturityScore:
    population_norm = min(1.0, inputs.n_cases / 500.0)
    components = {
        "coverage": inputs.coverage,
        "cosign_rate": inputs.cosign_rate,
        "variant_stability": inputs.variant_stability,
        "outcome_signal": inputs.outcome_signal,
        "population": population_norm,
    }
    score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
    return MaturityScore(score=score, band=_band(score), components=components)


__all__ = ["MaturityInputs", "MaturityScore", "compute", "js_divergence", "variant_stability"]
