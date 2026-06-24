# AEGIS Living — AI Transformation Assessment Platform
### by Fuzebox.AI · Layer 1: Executive Discovery

> **This is not an AI readiness survey. It is the front door to a multi-month
> transformation engagement.**

A single-file, no-framework web platform that, in **12–15 minutes**, tells a
senior-living executive where labor is wasted, where margin is leaking, and
where AI produces measurable ROI — then routes them into the next engagement.

Built bespoke for **Aegis Living** from their own discovery transcript: the
caregiver-documentation burden (~40% of a $180M line), ~64 disconnected systems,
the adult-child buyer, the 24-month length-of-stay margin tail, and the
predictive-health data moat.

---

## Run it

**Zero-dependency (just open it):**
```bash
open aegis/index.html          # macOS
# or: xdg-open aegis/index.html / double-click it
```
It is fully self-contained — routing, scoring, charts, ROI, and exports all run
in the browser. Works offline (web fonts degrade gracefully).

**As part of the FastAPI host (already wired):**
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5000
# → http://localhost:5000/aegis
```

**Deploy:** the repo already ships `render.yaml`. The assessment is live at
`/aegis` with no extra infrastructure.

---

## What it does

1. **Generates executive insight** — Stage (1–5), biggest gaps, biggest
   opportunities, value-at-stake. Not "you scored 3.8."
2. **Sells the next engagement** — every report ends in the 4-option funnel
   (Workshop · Diagnostic · Proof-of-Value · Program), recommending Phase 2.
3. **Minimizes effort** — adaptive routing shows only 15–20 of ~22 questions,
   tuned to role, department, and prior answers.
4. **Captures organizational intelligence** — confidence, evidence quality,
   variance, alignment, pain-point clustering, open-text themes.
5. **Produces consulting-grade outputs** — Executive Summary, Board Summary,
   Heat Map, Spider/Radar, AI Opportunity Matrix, ROI model, 30-60-90 plan,
   12-month roadmap, CSV/JSON export, HubSpot sync, print-to-PDF.

Try **"View a sample report"** on the landing page to see the full output suite
instantly with realistic Aegis answers.

---

## File map
```
aegis/
├── index.html                    ← the entire platform (HTML+CSS+JS, no deps)
├── README.md                     ← this file
├── HANDOFF.md                    ← build/extend guide (start here, LUCA)
└── docs/
    ├── DATA_MODEL.md             ← entities, exports, aggregation
    ├── QUESTION_BANK.md          ← question design + routing + Layers 2/3
    ├── SCORING_ENGINE.md         ← 12 dimensions, stages, ROI math
    ├── PROMPT_LIBRARY.md         ← LLM prompts for Layers 2/3 + reports
    ├── ADMIN_PORTAL_SPEC.md      ← back-office portal spec
    ├── MULTI_TENANT_ARCHITECTURE.md ← path to SaaS + API surface
    └── HUBSPOT_INTEGRATION.md    ← CRM sync + custom properties
```

## Extending to other industries
The 12-dimension core is industry-agnostic. Add a module by tagging questions
with a new `industry`, supplying an opportunity catalogue, and setting ROI
anchors. Selectors already scaffold automotive, hospitality, healthcare, media,
energy, and sports. See `QUESTION_BANK.md`.

---
© 2026 Fuzebox.AI — proprietary.
