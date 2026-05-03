# Threat Model — Sprint 5

## Assets

| Asset | Why it matters |
| --- | --- |
| PEL row chain | Tamper-evident economic ledger; auditor trust depends on it |
| Cosign event log | Records every webhook attempt; basis for unmatched-webhook diagnostics |
| Signing keys (KMS / Vault / static-HMAC) | Compromise → forged rows |
| Tenant data in `meta` JSONB | Contains business identifiers; isolated by RLS |
| SDK API keys | Authn for `/v1/pel/*`; per-tenant scoped |

## Trust boundaries

1. Customer agent process ↔ Cosigner API (in customer VPC)
2. Cosigner API ↔ Postgres (in customer VPC)
3. Cosigner API ↔ KMS / Vault (cross-account or in-VPC)
4. Customer VPC ↔ FuzeBox SaaS control plane (anonymized aggregates only;
   never row contents, span attributes, or signing material)

## STRIDE

### Spoofing
- Forged PEL row submission → blocked: every write goes through the SDK,
  which signs locally and submits via authenticated `/v1/pel/open`. Direct DB
  writes fail signature verification at audit time.
- Forged webhook → blocked: each adapter verifies HMAC + replay window.

### Tampering
- DB row tamper → detected by chain rehash + signature check in `verify.py`.
- Audit log tamper → detected by `cosign_event_log.event_hash` chain.

### Repudiation
- Cosigner refuses → SDK fails open and queues locally; reconciliation worker
  flushes when the cosigner returns. The audit log records every cosign
  attempt regardless of match outcome.

### Information disclosure
- PII in span text → Presidio + regex redactor at ingest path
  (`services/cosigner_api/app/pii/`).
- Cross-tenant read → Postgres RLS (`FORCE ROW LEVEL SECURITY`) plus
  `app.tenant_id` set per request.

### Denial of service
- Cosigner DoS → SDK fails open; agent never blocks. Reconciliation drains
  buffers when service returns.
- Webhook flood → idempotent on `(adapter, event_id)` so replays are 200s
  not new writes.

### Elevation of privilege
- KMS leakage → ECC-P256 KMS keys are non-exportable; Terraform module limits
  IAM to `kms:Sign`, `kms:Verify`, `kms:GetPublicKey`.
- Static HMAC in prod → guarded by `FUZEBOX_ALLOW_STATIC_SIGNING=1` env;
  `StaticHMACProvider` raises in `prod` without it.

## Out of scope (Sprint 5)

- DDoS at the network edge (customer's CDN / WAF).
- Compromise of the customer's K8s control plane.
- Compromise of the customer's KMS / Vault tenancy.
