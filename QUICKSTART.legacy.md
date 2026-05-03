# FuzeBox Telemetry — Quickstart

Run the full live dashboard locally on http://localhost:5000.

## Requirements
- Python 3.10+

## Run

```bash
unzip fuzebox-live.zip
cd fuzebox-live
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Then open: **http://localhost:5000**

Click **Seed Sample Data** to generate 60 synthetic executions, or hit the API directly:

```bash
# Health
curl http://localhost:5000/health

# Seed 60 executions
curl -X POST http://localhost:5000/v1/dev/seed?count=60

# Dashboard summary
curl http://localhost:5000/v1/dashboard/summary

# Full Swagger UI
open http://localhost:5000/docs
```

## SDK lifecycle test

```bash
BASE=http://localhost:5000

curl -X POST $BASE/v1/executions/start -H 'Content-Type: application/json' \
  -d '{"execution_id":"test1","skill_id":"brake_diagnosis","agent_id":"a1"}'

curl -X POST $BASE/v1/executions/test1/model-call -H 'Content-Type: application/json' \
  -d '{"model_provider":"openai","model_name":"gpt-4o-mini","prompt_tokens":120,"completion_tokens":40,"total_tokens":160,"cost_usd":0.0009,"latency_ms":420,"success":true}'

curl -X POST $BASE/v1/executions/test1/skill -H 'Content-Type: application/json' \
  -d '{"skill_id":"brake_diagnosis","executor":"hybrid","invocation_count":1,"success":true,"latency_ms":2000}'

curl -X POST $BASE/v1/executions/test1/outcome -H 'Content-Type: application/json' \
  -d '{"success":true,"outcome_value":48.5,"risk_score":0.05}'

curl -X POST $BASE/v1/executions/test1/end

curl $BASE/v1/executions/test1
```

## What you get
- **/** — Executive dashboard (KPIs, skills, models, executors, coordination-tax heatmap, ledger)
- **/docs** — Full Swagger UI for all v1 endpoints
- **/v1/executions/*** — Lifecycle ingest API
- **/v1/uef/decide** — Unified Executor Framework scoring
- **/v1/dashboard/*** — JSON aggregates powering the UI
- **/v1/dev/seed** · **/v1/dev/reset** — synthetic data utilities

Data persists in `data.db` (SQLite) in the project root.
