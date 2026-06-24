# AEGIS Living — Administrator Portal Specification

The Layer 1 app is respondent-facing. This spec defines the **back-office portal**
that consultants and the client admin use to configure, distribute, and analyze
assessments. It is a forward spec for the build LUCA will extend into; it maps
cleanly onto the multi-tenant architecture.

## Roles
| role | can |
|---|---|
| **Super Admin (Fuzebox)** | Manage tenants, question banks, modules, branding |
| **Engagement Lead** | Configure an org's assessment, invite respondents, read all analytics |
| **Org Admin (client)** | Invite their team, view their org's aggregate reports |
| **Respondent** | Take the assessment, see their own result |

## Modules

### 1. Tenant & branding
- Create org, pick industry module, set palette/logo (white-label).
- Toggle which layers are live (1 / 2 / 3).

### 2. Question bank manager
- CRUD on questions; edit option maturity values, dimension weights, ROI anchors.
- Versioning + publish/draft; preview routing for a given role/department.
- Import/export bank as JSON (same shape as `QUESTIONS`).

### 3. Distribution
- Generate per-respondent invite links (role/department pre-tagged).
- Email/SMS campaign integration (HubSpot/Marketing Orchestration Engine).
- Track started / completed / abandoned; nudge reminders.

### 4. Analytics workbench
- Org aggregate dashboard: transformation index, dimension heatmap, variance.
- **Role & department variance** with drill-down.
- Leadership-alignment spread; pain-point clustering across open-text.
- Evidence-quality and confidence overlays.
- Psychometric panel (Layer 2+): Cronbach's α, item discrimination, factor loadings.
- Cohort/benchmark comparison across orgs (anonymized) and over time.

### 5. Deliverable studio
- One-click generation of: Executive Summary, Board Summary, Heat Maps, Spider,
  AI Opportunity Matrix, 30-60-90, 12-month roadmap, ROI model.
- Export to PDF / PowerPoint / CSV / JSON.
- Prompt library (see `PROMPT_LIBRARY.md`) wired to the report generator.

### 6. CRM & funnel
- Sync completions to HubSpot (contact + `aegis_*` properties).
- Track which of the 4 next-step options each executive selected.
- Pipeline view: Assessment → Workshop → Diagnostic → PoV → Program.

### 7. Governance & audit
- Full audit trail of admin actions and any AI-generated content.
- PHI guardrails: the platform collects **no PHI**; enforce at config time.
- Data residency / retention controls per tenant (EU-grade by default).

## Non-functional
- SSO (SAML/OIDC) for admins; magic-link for respondents.
- Role-based access control on every endpoint.
- All analytics computed server-side from the `ResultProfile` data model.
