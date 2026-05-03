# ADR 0001 — Tech Stack

Status: Accepted
Date: 2026-05-03

## Context

The build prompt fixes the tech stack. This ADR records it verbatim and notes any
deviations made during Sprint 1.

## Fixed stack

- Languages: Python 3.11+, TypeScript 5+, SQL (Postgres dialect).
- Backend: FastAPI, SQLAlchemy 2 (async), Alembic, Celery + Redis, structlog.
- DB: Postgres 15 + TimescaleDB. Hypertables on `pel_rows`, `cosign_event_log`, `spans`.
- LLM gateway: LiteLLM (vendored as the only allowed call path from agent code).
- Tracing: OpenTelemetry SDK; OTLP to a local OTEL collector.
- Mining: PM4Py (Apache-2.0).
- PII: Microsoft Presidio in the customer VPC at ingest.
- Signing: AWS KMS (primary), HashiCorp Vault (fallback), static HMAC (dev only).
- Frontend: Next.js 14, NextAuth, Tailwind, shadcn/ui.
- Deploy: Helm chart, Terraform module (AWS EKS / GCP GKE / Azure AKS).
- CI: GitHub Actions.

## Sprint 1 deviations

None. Sprint 1 only exercises:

- Python 3.11 + FastAPI + SQLAlchemy 2 (async) + Alembic.
- Postgres 15 (TimescaleDB extension is created if available; tests fall back to plain Postgres).
- KMS / Vault / static-HMAC `SigningProvider` adapters; Sprint 1 demos use static HMAC.
- structlog for logging.
- GitHub Actions CI.

The remaining stack items (Celery, OpenTelemetry, PM4Py, Presidio, Next.js, Helm, Terraform)
land in later sprints.

## Notes

- TimescaleDB extension creation is conditional in the migration so that CI without the
  extension installed still runs. Hypertable creation is only attempted if the extension
  is present.
- For local dev without AWS, the static HMAC provider is used, gated by an explicit
  `signing.provider=static` config flag. The provider raises in production mode unless
  `FUZEBOX_ALLOW_STATIC_SIGNING=1` is set.
