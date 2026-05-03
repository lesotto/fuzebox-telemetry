# Changelog

All notable changes to FuzeBox AEOS Telemetry Engine.

## [Unreleased]

### Sprint 1 — Trust Foundations (in review)

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
