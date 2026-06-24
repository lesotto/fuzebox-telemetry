# AEGIS Living Assessment — Data Model

The platform captures **organizational intelligence**, not just scores. Every
session produces a structured record that feeds analytics, CRM, and the deeper
diagnostic layers. The model below is implemented client-side today (localStorage
+ JSON export) and maps 1:1 to the server-side / multi-tenant schema in
`MULTI_TENANT_ARCHITECTURE.md`.

## Core entities

```
Organization 1───* Respondent 1───1 Session 1───* Answer
     │                                   │
     │                                   └──1 ResultProfile 1───* DimensionScore
     └──* AggregateProfile                                  1───* Opportunity
                                                            1───1 ROIModel
```

### Organization
| field | type | notes |
|---|---|---|
| `org_id` | string (slug) | `aegis_living` |
| `name` | string | "Aegis Living" |
| `industry_module` | enum | `senior_living` \| `automotive` \| `hospitality` \| `healthcare` \| `media` \| `energy` \| `sports` |
| `created_at` | ISO datetime | |

### Respondent
| field | type | notes |
|---|---|---|
| `respondent_id` | string | hashed from name+role+timestamp |
| `name` | string | |
| `email` | string | routed to CRM |
| `role` | enum | `executive`/`operations`/`clinical`/`technology`/`finance`/`sales`/`frontline` |
| `department` | enum | `enterprise`/`care`/`operations`/`culinary`/`sales_marketing`/`finance`/`it_data`/`family` |

### Session
| field | type | notes |
|---|---|---|
| `session_id` | string | |
| `layer` | int | `1` = Executive Discovery (this app), `2` = Enterprise Diagnostic, `3` = Transformation |
| `started_at` / `completed_at` | datetime | drives the 12–15 min target |
| `routed_question_ids` | string[] | the adaptive subset shown (15–20 of the bank) |

### Answer
| field | type | notes |
|---|---|---|
| `question_id` | string | FK to question bank |
| `value` | number/string/array | normalized response |
| `maturity` | float 0–1 | mapped maturity contribution |
| `confidence` | int 0–100 | self-reported per question |
| `evidence_flag` | bool | derived (e.g. "we don't measure" → low evidence) |
| `metric_writes` | map | ROI inputs (e.g. `docShare`, `systems`) |

### ResultProfile
| field | type | notes |
|---|---|---|
| `transformation_index` | int 0–100 | overall weighted maturity |
| `stage` | {lvl 1–5, name} | Analog → Connected → Informed → Augmented → Autonomous |
| `readiness` / `execution` | int 0–100 | composite indices |
| `confidence` / `evidence` | int 0–100 | meta-quality scores |
| `priority` / `blocker` | enum | executive-stated direction |
| `themes` | {text, themes[], sentiment} | open-text NLP extraction |

### DimensionScore (×12)
| field | type | notes |
|---|---|---|
| `dimension_key` | enum | see `SCORING_ENGINE.md` |
| `score` | int 0–100 | weighted |
| `weight` | float | dimension weight |
| `opportunity` | float | value-weighted headroom (drives ranking) |

### Opportunity (catalogue, scored per org)
`name`, `dimension`, `impact` (0–1, gap-tuned), `feasibility` (0–1),
`quick_win` (bool), `value` (text), `tags[]`.

### ROIModel
`lines[] {label, value_usd, note}`, `total`, `low`, `high`, `invest`,
`roi_multiple`, `payback_months`. Anchored on Aegis-scale figures (see
`SCORING_ENGINE.md → ROI`).

### AggregateProfile (organization roll-up)
Computed across respondents for **variance & alignment**: role variance,
department variance, leadership-alignment spread, evidence quality, pain-point
clustering. Stored per-org and refreshed on each completion.

## Export formats
- **JSON** — full `ResultProfile` + answers (the canonical data model; `Export data model (JSON)`).
- **CSV** — flat profile/dimension/ROI/answer rows for spreadsheet & BI tools.
- **HubSpot** — contact + custom `aegis_*` properties (see `HUBSPOT_INTEGRATION.md`).
