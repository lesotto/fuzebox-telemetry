# AEGIS Living — HubSpot Integration

Every completed assessment is a qualified, richly-attributed lead. The platform
ships an **API-ready** integration: the client builds the payload; a serverless
proxy holds the token and writes to HubSpot.

## What gets synced
On completion (or when an executive selects a next-step option), the app builds a
HubSpot **contact** with custom assessment properties:

```json
{
  "email": "adam@aegisliving.com",
  "firstname": "Adam", "lastname": "Clark",
  "company": "Aegis Living", "jobtitle": "Executive",
  "properties": {
    "aegis_transformation_index": 47,
    "aegis_stage": "Informed",
    "aegis_value_at_stake": 24900000,
    "aegis_top_opportunity": "Ambient Care Documentation",
    "aegis_recommended_next_step": "Enterprise Transformation Diagnostic",
    "aegis_confidence": 72,
    "aegis_priority": "documentation",
    "aegis_blocker": "data",
    "aegis_completed_at": "2026-06-24T18:00:00Z"
  }
}
```

## Custom properties to create in HubSpot
Create these contact properties (group: *AI Transformation Assessment*):
`aegis_transformation_index` (number), `aegis_stage` (single-line),
`aegis_value_at_stake` (number, currency), `aegis_top_opportunity` (single-line),
`aegis_recommended_next_step` (dropdown: Workshop / Diagnostic / PoV / Program),
`aegis_confidence` (number), `aegis_priority` (single-line),
`aegis_blocker` (single-line), `aegis_completed_at` (date-time).

## Wiring it up (production)
The client **never** holds the HubSpot token. Point the app at a serverless
proxy:

```js
// before loading the app, or via env injection:
window.AEGIS_HUBSPOT_ENDPOINT = "https://api.fuzebox.ai/aegis/hubspot";
```

Minimal proxy (pseudo):
```js
// POST /aegis/hubspot
export default async (req, res) => {
  const token = process.env.HUBSPOT_PRIVATE_APP_TOKEN;     // server-side only
  const r = await fetch("https://api.hubapi.com/crm/v3/objects/contacts", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ properties: flatten(req.body) })
  });
  res.status(r.ok ? 200 : 502).json(await r.json());
};
```

## Demo behavior
With no endpoint configured, `pushHubspot()` logs the exact payload to the
console and shows a toast — so reviewers can see precisely what would sync
without any credentials.

## Funnel attribution
The 4 next-step options (Workshop / Diagnostic / PoV / Program) write
`aegis_recommended_next_step` and trigger a follow-up task — feeding the
Assessment → Workshop → Diagnostic → PoV → Program pipeline.
