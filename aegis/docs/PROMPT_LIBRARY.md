# AEGIS Living — Prompt Library

Reusable prompts for the (optional) AI-assisted layers: open-text theme
extraction, narrative generation, and the deeper diagnostics. The Layer 1 app
ships **without** runtime LLM calls (deterministic + privacy-safe); these
prompts power Layer 2/3 and the back-office report generator.

> Model guidance: default to the latest Claude models (e.g. Claude Opus / Sonnet
> 4.x). Keep PHI out of prompts — operate on de-identified aggregates only.

---

## 1. Open-text theme & sentiment extraction
```
System: You are an organizational psychometrician analyzing free-text responses
from a senior-living AI transformation assessment. Extract themes, sentiment,
and transformation signals. Never infer or output PHI.

User: Respondent role: {role}. Department: {dept}.
Response: "{open_text}"

Return JSON:
{ "themes": [up to 4 from: caregiver_time_back, unified_data, family_trust,
  margin_cost, risk_compliance, change_fatigue, growth],
  "sentiment": "optimistic|neutral|cautious",
  "executive_signal": "<one sentence: what this reveals about readiness>" }
```

## 2. Executive summary narrative
```
You are a McKinsey-grade transformation partner writing for a senior-living
executive. Given the scored profile, write a 3-paragraph executive read that:
(1) frames AI as operating-model redesign, not tool-buying;
(2) names the top 3 dimension gaps as where money/labor leak;
(3) states the value-at-stake band and the single recommended first move.
Tone: confident, specific, never generic. Use their numbers.

Input: {transformation_index, stage, top_gaps[], roi_band, top_opportunity}
```

## 3. Board summary (5 findings / 4 recommendations)
```
Write a confidential board summary. Exactly 5 findings (each one sentence,
quantified) and 4 recommended actions (each an approvable decision). Close with
"the ask": approve Phase 2 (Enterprise Transformation Diagnostic). No hedging.
Input: {profile_json}
```

## 4. AI opportunity rationale
```
For the opportunity "{name}" in dimension "{dimension}", write a 2-sentence
business case for a senior-living operator: the labor/margin/risk it moves and
why it is feasible now. Reference the Aegis context (caregiver documentation,
24-month length of stay, adult-child buyer, ~64 systems) where relevant.
```

## 5. Proof-of-Value Sprint brief
```
Draft a 30–60 day Proof-of-Value brief for "{priority_area}". Include: the one
problem, the baseline metric, the intervention, the measured success metric, the
data required, and the governance/audit checkpoint. One page.
```

## 6. Layer-2 question generation (for new dimensions/industries)
```
Generate 6 assessment questions for the dimension "{dimension}" in the
"{industry}" module. Rules: each must uncover money/labor/risk/growth; include a
"why this matters" line; provide 4–5 options with maturity values 0–1 and an
opportunity signal; never ask generic AI-literacy questions.
Return the JSON shape used by the QUESTIONS array.
```

## 7. Variance interpreter (multi-respondent)
```
Given dimension scores from {n} leaders across roles, identify the 2 largest
alignment gaps and explain each as either "conviction without capacity" or
"capability without mandate". Recommend the workshop focus.
Input: {variance_rows_json}
```
