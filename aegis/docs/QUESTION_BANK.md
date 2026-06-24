# AEGIS Living — Question Bank & Routing

The bank is the heart of the platform. Every question is designed to **uncover
money, labor, risk, growth, or competitive advantage** — never generic AI
literacy. The full machine-readable bank lives in the `QUESTIONS` array in
`aegis/index.html`; this document is the human-readable spec.

## Design rules
- **Never** ask "Do you use AI?" — ask "How many caregiver hours go to
  documentation that could be care?"
- Every question carries a **`Why this matters`** line grounded in Aegis reality.
- Every question maps to ≥1 of the 12 dimensions with sub-weights.
- Every question can write **ROI metrics** and carries a **confidence** slider.

## Routing engine (Layer 1: 15–20 of ~22 shown)
`routeQuestions(profile)` does:
1. **Industry filter** — `senior_living` sees the full bank; other modules see
   the `any` core (industry-agnostic dimensions).
2. **Relevance scoring** — base `priority` + boosts for dimensions in the
   respondent's role/department focus map.
3. **Coverage guarantee** — pass 1 ensures every one of the 12 dimensions is
   touched at least once; pass 2 fills by relevance up to ~17.
4. **Flow ordering** — sections ordered Strategic → Workforce → Data → Family →
   Clinical → Financial → Governance → Leadership; open-text reflection last.

Role focus maps (`ROLE_DIM_FOCUS`) and department bias (`DEPT_BIAS`) are the
routing knobs — e.g. a **Clinical** leader is steered toward `clinical`,
`workforce`, `governance`, `change`; a **Finance** leader toward `finance`,
`data`, `ops`, `strategy`.

## Layer 1 bank (Executive Discovery — this app)

| id | section | dimensions | uncovers |
|---|---|---|---|
| `amb` | Strategic Context | strategy | Operating-model ambition vs. pilots |
| `urgency` | Strategic Context | strategy, change | Demand-curve urgency (74M turning 80) |
| `doc_hours` | Workforce & Care | workforce, ops | Caregiver time lost to documentation |
| `ambient` | Workforce & Care | workforce, clinical, execution | Ambient-AI readiness |
| `staffing` | Workforce & Care | ops, finance, clinical | Acuity-based staffing |
| `unified` | Data & Architecture | data, ops | Cross-domain analysis without reconciliation |
| `sys_count` | Data & Architecture | tech, ops | System sprawl (the ~64) |
| `reporting` | Data & Architecture | data, ops, execution | Push intelligence vs. 50 reports |
| `dynamics` | Data & Architecture | tech, strategy | Orchestration layer vs. a platform |
| `family_comm` | Family & Experience | family | Proactive adult-child communication |
| `crm_use` | Family & Experience | family, data | CRM lifecycle vs. sales-only |
| `predictive` | Clinical & Predictive | clinical | Falls/UTIs/hydration/cognitive prediction |
| `los` | Clinical & Predictive | clinical, finance | Length-of-stay as a financial lever |
| `occupancy` | Financial | finance | Dynamic pricing & occupancy |
| `culinary` | Financial | finance, ops | Culinary forecasting & buying power |
| `governance` | Governance & Risk | governance | AI audit trail & explainability |
| `privacy` | Governance & Risk | governance, data | PHI governance across systems |
| `alignment` | Leadership & Change | alignment | Ownership-group conviction |
| `change_app` | Leadership & Change | change | Community-level adoption pattern |
| `execution` | Leadership & Change | execution, tech | Pilot-to-production reliability |
| `invest` | Leadership & Change | strategy, execution | One-area investment priority → PoV target |
| `blocker` | Leadership & Change | change, execution | Top transformation blocker |
| `priorities_text` | Leadership & Change | — | Open-text (NLP theme extraction) |

## Layer 2 — Enterprise Transformation Diagnostic (85 questions)
Expands each dimension to 6–8 items for **psychometric reliability**, adds:
- Role-specific & department-specific branches (Care, Culinary, Sales,
  Finance, IT/Data, Family Experience).
- **Evidence collection** (attach a metric / document per claim).
- Leadership-alignment instrument (same items to every executive → variance).
- Technology inventory capture (toward the ~64-system map).

## Layer 3 — Transformation Assessment (185+ questions)
Workshop-driven, cross-functional. Adds process maps, resident & family journey
maps, use-case prioritization, and the implementation/measurement plan. This is
where the assessment becomes the engagement.

## Reusing the engine for other industries
Add a module by tagging questions with a new `industry` value and supplying an
industry opportunity catalogue + ROI anchors. The 12-dimension core is
industry-agnostic; only the question surface and dollar anchors change.
Examples scaffolded in the role/industry selectors: automotive retail,
hospitality, healthcare, media, energy, sports.
