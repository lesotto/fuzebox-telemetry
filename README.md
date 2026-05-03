# FuzeBox AEOS Telemetry Engine

A signed, hash-chained economic ledger of every AI agent execution, mined into a
process map and shipped as a Helm chart that deploys into the customer's own
Kubernetes cluster.

> **Status: Sprint 1 — Trust Foundations.** SDK opens a row, server signs and
> chains it, `verify.py` validates the chain offline. See
> [`CHANGELOG.md`](./CHANGELOG.md) for details.

The legacy single-process v1 telemetry app is preserved at `app/`,
[`README.legacy.md`](./README.legacy.md), and `render.yaml` for reference.

---

## Quickstart (local dev)

```bash
# 1. Bring up Postgres + the cosigner API
docker compose up -d postgres
export FUZEBOX_DATABASE_URL='postgresql+asyncpg://fuzebox:fuzebox@localhost:5432/fuzebox'
export FUZEBOX_SIGNING_PROVIDER=static
export FUZEBOX_STATIC_SIGNING_KEY=dev-static-signing-key

# 2. Run migrations
python -m alembic -c services/cosigner_api/alembic.ini upgrade head

# 3. Start the API
uvicorn services.cosigner_api.app.main:app --reload --port 8080

# 4. From another shell, exercise the SDK
python - <<'PY'
import fuzebox
fuzebox.init(api_key="local", tenant="acme", endpoint="http://localhost:8080")
with fuzebox.open_pel_row(skill="claims_triage",
                          meta={"stripe_payment_intent_id": "pi_test"}) as row:
    row.set_predicted_outcome_usd(50)
    print("row_id:", row.row_id, "status:", row.status)
PY
```

## Public SDK contract

```python
import fuzebox

fuzebox.init(api_key="...", tenant="acme", endpoint="https://fuzebox.acme.com")

with fuzebox.open_pel_row(
    skill="claims_triage",
    meta={"stripe_payment_intent_id": pi_id},
) as row:
    result = my_agent.run(claim)
    row.set_predicted_outcome_usd(result.estimated_savings)
```

The SDK never blocks the agent. If the cosigner is unreachable, rows go to a
local SQLite buffer and are reconciled later — the row stays tagged
`unledgered` until the cosigner confirms it.

## Repo layout

```
sdk-python/                Python SDK
sdk-typescript/            TS SDK (Sprint 4)
services/
  cosigner_api/            FastAPI signing + ledger service
  miner/                   PM4Py-backed process miner (Sprint 3)
  reconciliation_worker/   Celery flusher (Sprint 5)
  verify_cli/verify.py     30-line offline auditor verifier
dashboard/                 Next.js (Sprint 4)
helm/fuzebox/              Helm chart (Sprint 4)
terraform/                 EKS module (Sprint 4)
benchmarks/                CI perf gates (Sprint 5 blocking)
docs/adr/                  Architecture decision records
```

## Tests

```bash
pytest services/cosigner_api/tests/ sdk-python/tests/ \
  --cov=services/cosigner_api/app --cov=sdk-python/src/fuzebox \
  --cov-report=term --cov-fail-under=80
```

Postgres integration tests skip unless `FUZEBOX_TEST_DATABASE_URL` is set.

## Sprint plan

See [`CHANGELOG.md`](./CHANGELOG.md). Each sprint ends with a runnable demo and
an open PR for review.

## License

Proprietary — FuzeBox Inc.
