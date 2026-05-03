# Changelog

All notable changes to FuzeBox AEOS Telemetry Engine.

## [Unreleased]

### Sprint 3 — Miner + Counterfactual + Twin Maturity

**Goal:** Mine 500 synthetic claims-triage cases, recover 3 planted variants,
counterfactual returns confidence-rated lifts, Twin Maturity Score lands in
the 40–60 band on a thin pilot.

#### Added

- `services/miner/app/miner.py` — variant + transition discovery. PM4Py
  Inductive Miner integration when installed; deterministic fallback otherwise.
  Subsamples to 25% above an event-count threshold and tags the artifact.
- `services/miner/app/counterfactual.py` — four-tier simulator
  (holdout / process-twin replay / variant average / synthetic). Confidence
  threshold of 0.30 enforced; below that, no `lift_usd`.
- `services/miner/app/maturity.py` — Twin Maturity Score with the 5-component
  weighted formula and JS-divergence variant-stability metric.
- `services/miner/app/prioritizer.py` — hourly/daily/weekly tier assignment
  by `volume × economic_exposure`.
- 21 new tests covering all four counterfactual tiers, variant recovery,
  transition stats, perf (<1s on 500 cases), maturity scoring + bands,
  prioritizer tier assignment.

#### Demo

`python scripts/sprint3_demo.py` — mines 500 cases in ~1.5 ms, recovers all 3
planted variants, runs counterfactuals across the population, computes Twin
Maturity Score 91 (production-ready band).

### Sprint 2 — Cosign + Stripe + Salesforce + PII

**Goal:** SDK opens a row tagged with `stripe_payment_intent_id`. A Stripe
webhook arrives. Row bumps T1 → T3. `lift_usd` populates. PII is redacted at ingest.

#### Added

- `services/cosigner_api/app/adapters/` — `CosignAdapter` ABC + `StripeAdapter`
  (HMAC-SHA256 with replay-window enforcement) + `SalesforceAdapter`
  (HMAC-SHA256 base64).
- `services/cosigner_api/app/ledger/cosign.py` — full state machine: idempotent
  on `(adapter, event_id)`, matches by `meta` JSONB, bumps trust to T3,
  re-links + re-signs the row, and appends a chained signed entry to
  `cosign_event_log`.
- `services/cosigner_api/app/routes/webhooks.py` — `POST /v1/webhooks/cosign/{adapter}`.
- `services/cosigner_api/app/pii/` — Presidio-aware PII redactor with regex fallback
  (credit card, SSN, email, phone). Idempotent.
- `sdk-python/src/fuzebox/litellm_wrapper.py` — auto-instrumentation of
  `litellm.completion` / `acompletion`. Cost is accumulated on the active row
  via a `ContextVar`; lands in `meta.litellm_cost_usd` on close.
- Tests: `test_adapters.py` (Stripe + Salesforce sign/verify/parse,
  replay rejection), `test_pii.py`, `test_webhook_routes.py`,
  `test_litellm_wrapper.py`, `test_cosign_postgres.py` (Postgres-gated:
  match → T3 → lift, idempotency, audit-log chain links, lift threshold).

#### Demo

`python scripts/sprint2_demo.py` — verifies a Stripe-signed payload, parses
`pi_demo_42`, computes lift = $10 against a $40 counterfactual at 0.85
confidence, redacts a credit card / SSN / email from a customer note, and
rejects a replayed event.

### Sprint 1 — Trust Foundations (merged)

**Goal:** SDK opens a row in a local Postgres. Row is HMAC-signed. `verify.py`
confirms a 100-row chain offline in under 5 seconds.

#### Added

- `services/cosigner_api/` — FastAPI service with `POST /v1/pel/open`,
  `POST /v1/pel/{row_id}/close`, `GET /health`.
- `services/cosigner_api/app/ledger/`:
  - `chain.py` — canonical SHA-256 hash chain over an explicit field allowlist.
  - `signing.py` — `SigningProvider` ABC plus `StaticHMACProvider`,
    `KMSProvider` (AWS KMS ECDSA), `VaultProvider` (HashiCorp Vault Transit).
  - `repo.py` — async repo with `open_row`, `close_row`, `get_chain`. Sets
    `app.tenant_id` so RLS enforces isolation at the database level.
  - `models.py` — SQLAlchemy 2 models for `pel_rows`, `spans`, `cosign_event_log`.
- `services/cosigner_api/alembic/versions/0001_initial_schema.py` — initial
  schema with TimescaleDB hypertable conversion (gracefully degrades on plain
  Postgres) and per-table RLS policies.
- `services/verify_cli/verify.py` — 30-line offline verifier. No network. Exit
  code only. Validates a 100-row chain in well under 5 s.
- `sdk-python/` — Python SDK with `init`, `open_pel_row` context manager,
  fail-open SQLite buffer (100 MB cap).
- Tests:
  - `services/cosigner_api/tests/` — chain, signing, route smoke, verify.py
    subprocess round-trip, Postgres integration tests (skipped without
    `FUZEBOX_TEST_DATABASE_URL`).
  - `sdk-python/tests/` — buffer, init idempotency, fail-open behaviour, no-init
    safety net.
  - 38 passing tests; 84% line coverage overall, 89%–100% on Sprint 1
    acceptance modules (`ledger/`, `signing.py`, SDK core).
- `.github/workflows/ci.yml` — lint (ruff) + type-check (mypy) + test (pytest +
  coverage gate at 80%); Postgres 15 service container; non-blocking benchmark
  job.
- `benchmarks/sdk_hot_path.py` — SDK overhead microbenchmark; advisory in
  Sprint 1, becomes a CI gate in Sprint 5.
- `docker-compose.yml`, `services/cosigner_api/Dockerfile` — local dev stack.
- `docs/adr/0001-tech-stack.md` — fixed stack and Sprint 1 deviations (none).

#### Sprint 1 acceptance

- [x] Postgres + TimescaleDB schema, Alembic migrations, RLS policies.
- [x] SDK Python skeleton with `init` and `open_pel_row` context manager.
- [x] KMS + Vault + static signing providers behind `SigningProvider` ABC.
- [x] `verify.py` runs offline, walks chain, validates signatures.
- [x] Cosigner API endpoints `POST /v1/pel/open` and `POST /v1/pel/close`.
- [x] CI: lint + type-check + test on every PR; bench job non-blocking.
- [x] Unit coverage ≥ 80% on `ledger/`, `signing.py`, SDK core.
- [x] `verify.py` validates a chain produced by the SDK in < 5 s.
