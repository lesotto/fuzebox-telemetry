/**
 * FuzeBox AEOS Telemetry SDK — TypeScript / Node.
 *
 * Mirrors the Python SDK contract:
 *
 *   import { fuzebox, openPelRow } from '@fuzebox/sdk';
 *   fuzebox.init({ apiKey, tenant, endpoint });
 *
 *   await openPelRow({ skill: 'claims_triage', meta: { stripe_payment_intent_id } },
 *     async (row) => {
 *       const result = await myAgent.run(claim);
 *       row.setPredictedOutcomeUsd(result.estimatedSavings);
 *     });
 */

export { fuzebox } from './client.js';
export { openPelRow } from './pel.js';
export type { InitOptions } from './client.js';
export type { PelRow } from './pel.js';
