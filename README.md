# FuzeBox Telemetry & Execution Intelligence — v1

> **LiteLLM measures the model call. FuzeBox measures the work.**

A vendor-agnostic, OpenTelemetry-compatible execution telemetry layer for AI agents. Records outcomes, coordination tax, skill efficiency, and unified executor scoring across humans, agents, and hybrids.

## Quick Deploy to Render (free)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Click the button → connect this GitHub repo → Render auto-detects `render.yaml` and deploys. Public URL is ready in ~3 minutes.

## Run Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Then open http://localhost:5000.

## Surface

| Path | What |
|---|---|
| `/` | Executive dashboard (KPIs, skills, models, executors, coord-tax heatmap, ledger) |
| `/docs` | Full Swagger UI for the v1 API |
| `/health` | Liveness check |
| `/v1/executions/start` | Begin tracking an execution |
| `/v1/executions/{id}/model-call` | Record a model invocation |
| `/v1/executions/{id}/tool-call` | Record a tool/function call |
| `/v1/executions/{id}/skill` | Record a skill invocation (executor: agent/human/hybrid) |
| `/v1/executions/{id}/human-step` | Record a human-in-the-loop step |
| `/v1/executions/{id}/outcome` | Record success + business value + risk |
| `/v1/executions/{id}/end` | Close out the execution |
| `/v1/executions/{id}` | Read full execution record |
| `/v1/uef/decide` | Unified Executor Framework — score paths and pick |
| `/v1/dashboard/{summary,skills,models,executors,coordination-tax,executions}` | JSON aggregates |
| `/v1/dev/seed?count=60` | Generate synthetic data for demo |
| `/v1/dev/reset` | Wipe all telemetry |

## Try It

```bash
BASE=https://<your-render-url>

# Seed sample data
curl -X POST $BASE/v1/dev/seed

# Inspect what got recorded
curl $BASE/v1/dashboard/summary | jq

# Record a real lifecycle
curl -X POST $BASE/v1/executions/start -H 'Content-Type: application/json' \
  -d '{"execution_id":"test1","skill_id":"brake_diagnosis","agent_id":"a1"}'

curl -X POST $BASE/v1/executions/test1/model-call -H 'Content-Type: application/json' \
  -d '{"model_provider":"openai","model_name":"gpt-4o-mini","prompt_tokens":120,"completion_tokens":40,"total_tokens":160,"cost_usd":0.0009,"latency_ms":420,"success":true}'

curl -X POST $BASE/v1/executions/test1/skill -H 'Content-Type: application/json' \
  -d '{"skill_id":"brake_diagnosis","executor":"hybrid","invocation_count":1,"success":true,"latency_ms":2000}'

curl -X POST $BASE/v1/executions/test1/outcome -H 'Content-Type: application/json' \
  -d '{"success":true,"outcome_value":48.5,"risk_score":0.05}'

curl -X POST $BASE/v1/executions/test1/end
curl $BASE/v1/executions/test1 | jq
```

## Architecture

- **FastAPI** — single-process, async, OpenAPI-generated docs at `/docs`
- **SQLite** — zero-ops storage, persisted on Render's free disk at `/var/data/data.db`
- **Jinja2** — server-rendered dashboard, no JS framework dependency
- **Pure Python** — no external service requirements, no LLM calls at runtime, OTel-compatible

## License

Proprietary — FuzeBox Inc.
