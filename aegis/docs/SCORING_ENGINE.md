# AEGIS Living — Scoring Engine

All scoring is deterministic and runs client-side in `aegis/index.html`
(`computeResults()`). No server round-trip, no LLM call at runtime.

## 1. The 12 dimensions (weighted)

| key | dimension | weight |
|---|---|---|
| `strategy` | Strategic Clarity & Ambition | 1.0 |
| `data` | Data Foundation & Unification | **1.3** |
| `ops` | Operational Efficiency & Coordination Tax | 1.2 |
| `workforce` | Workforce Augmentation & Caregiver Capacity | **1.3** |
| `family` | Customer & Family Experience | 1.1 |
| `clinical` | Clinical & Predictive Intelligence | 1.2 |
| `finance` | Financial & Revenue Optimization | 1.1 |
| `tech` | Technology & Architecture Readiness | 1.1 |
| `governance` | Governance, Risk & Compliance | 1.0 |
| `change` | Change Readiness & Adoption Culture | 1.0 |
| `alignment` | Leadership Alignment | 1.0 |
| `execution` | AI Maturity & Execution Capacity | 1.1 |

Weights reflect the Aegis thesis: **data** and **workforce** carry the most
leverage (the unified-intelligence layer and the caregiver-documentation burden).

## 2. From answer → dimension score

1. Each answer maps to a **maturity value** `v ∈ [0,1]` (choice options and
   5-point scales carry calibrated values).
2. Each question declares the dimensions it informs and a sub-weight `w`:
   `dims: [{k:'data', w:1}, {k:'ops', w:0.4}]`.
3. Dimension score = weighted mean of contributing answers:
   `score_d = Σ(v·w) / Σ(w)` → scaled to 0–100.
4. **Overall Transformation Index** = `Σ(score_d · weight_d) / Σ(weight_d)`.

## 3. Maturity stages

| index | stage | meaning |
|---|---|---|
| 0–29 | 1 · Analog | Person-dependent, siloed, manual coordination |
| 30–47 | 2 · Connected | Systems exist but rarely speak; heavy reporting |
| 48–65 | 3 · Informed | Data trusted in places; first AI pilots |
| 66–81 | 4 · Augmented | AI gives time back; intelligence reaches decisions |
| 82–100 | 5 · Autonomous | Orchestrated operating model; agents in production |

## 4. Meta-scores

- **Confidence** — mean of per-question confidence sliders (0–100).
- **Evidence quality** — confidence-weighted, penalized when answers signal
  "we don't measure / undecided / no one can say" (low-evidence flags).
- **Opportunity intensity** (per dimension) — `Σ(opp_signal · w)` where
  `opp_signal` is the question's explicit `opp` value or `(1 − v)`. This drives
  the "biggest opportunities" ranking — it surfaces **value-weighted headroom**,
  not just low scores.
- **Readiness** = mean(`data`,`tech`,`governance`,`change`,`alignment`).
- **Transformation** = mean(`strategy`,`data`,`ops`,`execution`).
- **Execution** = mean(`execution`,`change`,`alignment`,`tech`).

## 5. Variance & alignment

When multiple respondents from one org complete the assessment (tracked by
`org_id` in localStorage; server-side in production), the engine computes:
- **You vs. senior-living benchmark** per dimension.
- **Role / department variance** — distribution of each dimension across roles.
- **Alignment gap** — spread (max−min) of overall index across leaders. A wide
  spread is the headline finding: *conviction without capacity* or vice-versa.

## 6. ROI model (Aegis-anchored)

Conservative, hypothesis-grade. Anchors are taken from the discovery transcript:

| anchor | value | source |
|---|---|---|
| Revenue tied to documentation pipeline | ~$180M (≈40% of top line) | transcript |
| Caregiver labor base | ~$135M (≈ debt service) | transcript |
| Culinary cost base | ~$28M (~9,000 plates/day) | transcript |

Six modeled levers, each scaled by the relevant **maturity gap** `(1 − score)`:
1. Caregiver capacity reclaimed (ambient documentation)
2. Retention / length-of-stay lift (the 55–60% margin tail months)
3. Occupancy & revenue management (dynamic pricing)
4. Family conversion & referrals (the ~30% channel that broke in COVID)
5. Culinary & supply optimization (forecast + pooled buying)
6. Coordination-tax reduction (orchestration over ~64 systems)

Output: `total`, a `low–high` band (0.6×–1.25×), a year-1 program envelope
(~$1.6M), an ROI multiple, and a payback in months. Presented explicitly as a
**hypothesis to be validated by a Proof-of-Value Sprint**, not a promise.

## 7. Calibration & governance

- All option values, weights, and ROI anchors live in one place (the
  `QUESTIONS`, `DIMENSIONS`, and `computeROI` blocks) for transparent tuning.
- Layer 2/3 add psychometric reliability (Cronbach's α), question
  discrimination, and factor analysis across the larger item bank — see
  `QUESTION_BANK.md`.
