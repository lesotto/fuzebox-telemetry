# Operator Runbook (Sprint 1)

This runbook is a stub for Sprint 1. It documents the operational surface that
exists today; later sprints flesh out upgrade, key rotation, backup/restore,
and pilot-onboarding procedures.

## Deploy (local dev)

```bash
docker compose up -d postgres
python -m alembic -c services/cosigner_api/alembic.ini upgrade head
uvicorn services.cosigner_api.app.main:app --port 8080
```

## Health

- `GET /health` → `{"status":"ok","version":"0.1.0"}`

## Configuration

Every value has an env-var override (see `services/cosigner_api/app/settings.py`):

| Env var | Default | Purpose |
| --- | --- | --- |
| `FUZEBOX_DATABASE_URL` | `postgresql+asyncpg://fuzebox:fuzebox@localhost:5432/fuzebox` | DB DSN |
| `FUZEBOX_SIGNING_PROVIDER` | `static` | `static` \| `kms` \| `vault` |
| `FUZEBOX_STATIC_SIGNING_KEY` | dev placeholder | HMAC secret |
| `FUZEBOX_KMS_KEY_ID` | (unset) | required for `kms` |
| `FUZEBOX_VAULT_ADDR` / `_TOKEN` / `_KEY` | (unset) | required for `vault` |
| `FUZEBOX_ENVIRONMENT` | `dev` | `dev` \| `staging` \| `prod` |
| `FUZEBOX_ALLOW_STATIC_SIGNING` | `0` | refuse static signing in prod unless `1` |

## Key rotation

Sprint 5 work. For Sprint 1:

- Static keys rotate by changing `FUZEBOX_STATIC_SIGNING_KEY` and re-deploying;
  existing rows remain verifiable using the old key from the audit bundle.
- KMS rotation is upstream (AWS KMS auto-rotation). The `key_id` in
  `signing.public_material()` is what auditors carry forward.

## Incident: cosigner unavailable

The SDK fails open. Rows buffer locally on the agent host (SQLite, 100 MB cap).
When the cosigner returns, the reconciliation worker (Sprint 5) flushes the
buffer. Until then rows are tagged `unledgered`.

## Auditing

Use `services/verify_cli/verify.py`:

```bash
python services/verify_cli/verify.py path/to/bundle.json
```

Exit `0` on success, non-zero on chain or signature mismatch.
