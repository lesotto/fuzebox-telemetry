# AEGIS Living — Multi-Tenant & API Architecture

How the single-file Layer 1 app grows into a multi-tenant SaaS platform without
rewriting the engine. The scoring/routing engine is already isolated and
portable — it can run client-side (today) or be lifted server-side unchanged.

## Today (Layer 1, shipped)
```
Browser ──> aegis/index.html  (routing · scoring · ROI · render)
                │
                ├─ localStorage  (org aggregate, multi-respondent variance)
                ├─ CSV / JSON export
                └─ HubSpot payload (POST via serverless proxy)
```
Served as a static file by the existing FastAPI app at `/aegis`. No DB required
to demo; fully functional offline (fonts degrade gracefully).

## Production (multi-tenant)
```
                       ┌────────────────────────────┐
   Respondents ──────> │  Web app (static SPA, CDN)  │
   Admins ───────────> │  Admin portal (SPA)         │
                       └─────────────┬──────────────┘
                                     │ HTTPS / JWT
                       ┌─────────────▼──────────────┐
                       │  API (FastAPI)             │
                       │  /v1/assessments           │
                       │  /v1/sessions              │
                       │  /v1/orgs/{id}/aggregate   │
                       │  /v1/questionbank          │
                       │  /v1/exports/{pdf,pptx,csv}│
                       └───┬─────────┬──────────┬───┘
                           │         │          │
                   ┌───────▼──┐  ┌───▼────┐  ┌──▼────────┐
                   │ Postgres │  │ Object │  │ Integr.   │
                   │ (RLS per │  │ store  │  │ HubSpot   │
                   │  tenant) │  │ (PDFs) │  │ /CRM/SSO  │
                   └──────────┘  └────────┘  └───────────┘
```

## Tenancy model
- **Row-level security** keyed by `org_id` on every table (Postgres RLS).
- One shared question-bank library + per-tenant overrides/versions.
- Per-tenant branding, enabled layers, and industry module.
- Anonymized cross-tenant benchmarking is opt-in and aggregate-only.

## API surface (maps to the data model)
| method | path | purpose |
|---|---|---|
| `POST` | `/v1/sessions` | start a session (org, respondent, layer) |
| `PUT` | `/v1/sessions/{id}/answers` | submit answers + confidence |
| `POST` | `/v1/sessions/{id}/score` | run engine → ResultProfile |
| `GET` | `/v1/orgs/{id}/aggregate` | variance / alignment / clustering |
| `GET` | `/v1/questionbank?industry=` | routed bank for a profile |
| `POST` | `/v1/exports` | render PDF / PPTX / CSV / JSON |
| `POST` | `/v1/integrations/hubspot` | sync contact + `aegis_*` props |

The existing FuzeBox Telemetry API (`/v1/executions/*`, `/v1/uef/decide`) is the
**measurement substrate**: once opportunities move to implementation, the same
ledger measures the work (coordination tax, executor scoring, ROI) — closing the
loop from assessment → execution intelligence.

## Engine portability
`computeResults`, `routeQuestions`, `computeROI`, and the `QUESTIONS` /
`DIMENSIONS` definitions are pure functions of input data. They can be:
1. Run in the browser (current).
2. Extracted to a shared JS/TS package and run in a Node serverless function.
3. Re-implemented server-side for authoritative scoring (the math is in
   `SCORING_ENGINE.md`).

## Security & compliance
- **No PHI collected** at Layer 1; enforce at schema + config.
- EU-grade governance defaults: audit trail, explainability, retention controls.
- SSO (SAML/OIDC) for admins, magic-link for respondents.
- Secrets (HubSpot token, etc.) never in the client — always behind the API.

## Deployment
- Static SPA → any CDN / static host.
- API → the existing `render.yaml` pattern (FastAPI + managed Postgres).
- The current repo already deploys the FastAPI host to Render free tier; the
  assessment is live at `/aegis` with zero additional infra.
