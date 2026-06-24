# Handoff Guide — for LUCA

Everything you need to take this from a working Layer-1 platform to production.
Read this first, then `README.md`, then the `docs/`.

## TL;DR
- The **entire Layer 1 product is one file**: `aegis/index.html`. No build step,
  no npm install, no framework. Open it in a browser and it works.
- It is **already wired** into the existing FastAPI app at route `/aegis`
  (`app/main.py`), so it deploys with the current `render.yaml` as-is.
- The `docs/` folder is the spec for Layers 2/3, the admin portal, multi-tenant
  SaaS, scoring math, and the CRM integration.

## How to verify it works (60 seconds)
```bash
# Option A — just open it
open aegis/index.html        # then click "View a sample report"

# Option B — automated smoke test (Node)
npm install jsdom --no-save
node -e '
const {JSDOM}=require("jsdom");const fs=require("fs");
const w=new JSDOM(fs.readFileSync("aegis/index.html","utf8"),
  {runScripts:"dangerously",pretendToBeVisual:true,url:"http://localhost/"}).window;
w.AEGIS.showSample();
console.log("Tabs:", w.document.querySelectorAll(".tab").length,
            "| Bubbles:", w.document.querySelectorAll(".bubble").length);
'
# expect: Tabs: 9 | Bubbles: 10
```

## Where everything lives (inside `index.html`)
| concern | symbol | what to change |
|---|---|---|
| 12 dimensions + weights | `DIMENSIONS` | rename, reweight |
| question bank | `QUESTIONS` | add/edit items, options, ROI metrics |
| routing logic | `routeQuestions()`, `ROLE_DIM_FOCUS`, `DEPT_BIAS` | tune which questions show |
| scoring | `computeResults()` | dimension math, stages, meta-scores |
| ROI model | `computeROI()` | anchors ($180M etc.), capture rates |
| opportunity catalogue | `scoreOpportunities()` | the 10 AI opportunities |
| charts | `radarSVG()`, `heatColor*()` | visuals (pure SVG, no libs) |
| exports | `exportCSV/exportJSON` | data formats |
| HubSpot | `pushHubspot()` | set `window.AEGIS_HUBSPOT_ENDPOINT` |
| branding/palette | `:root` CSS vars | green palette, fonts |

## Recommended build order
1. **Stand up the API** per `docs/MULTI_TENANT_ARCHITECTURE.md` (FastAPI +
   Postgres with row-level security). Reuse the engine math from
   `docs/SCORING_ENGINE.md` for authoritative server-side scoring.
2. **Persist sessions** server-side (today it's localStorage). The data model is
   in `docs/DATA_MODEL.md` and the JSON export already matches it.
3. **Wire HubSpot** via a serverless proxy (`docs/HUBSPOT_INTEGRATION.md`) — the
   client payload is already built; you just hold the token server-side.
4. **Build the admin portal** per `docs/ADMIN_PORTAL_SPEC.md` (question-bank
   manager, analytics workbench, deliverable studio).
5. **Expand the question bank** to Layer 2 (85 Q) / Layer 3 (185 Q) using
   `docs/QUESTION_BANK.md` and the generation prompt in `docs/PROMPT_LIBRARY.md`.
6. **Report generator** — PDF/PPTX export using the prompts in
   `docs/PROMPT_LIBRARY.md` (default to latest Claude models; keep PHI out).

## Guardrails / non-negotiables
- **No PHI** is collected anywhere in Layer 1. Keep it that way; enforce in schema.
- **Secrets never in the client** — HubSpot/CRM tokens behind the API only.
- Keep the **"why this matters"** line on every question — it is what makes
  executives feel understood. Never regress to generic AI-literacy questions.
- The ROI figures are **hypotheses, labeled as such** — don't present them as
  promises. The Proof-of-Value Sprint converts them to measured numbers.

## Dependencies
- **Layer 1 runtime:** none.
- **Host (optional):** Python deps in `requirements.txt` (FastAPI + uvicorn).
- **Tests:** `jsdom` (dev only, `--no-save`).

## Contact / context
Source grounding: the Aegis discovery call transcript and Fuzebox product docs.
Key anchors that must stay consistent across all materials: ~64 systems,
~$180M / 40% documentation-linked revenue, ~$135M caregiver labor, ~9,000
plates/day, 24-month length of stay (55–60% margin tail), ~30% family-referral
channel, fall prevention as the #1 clinical wedge.
