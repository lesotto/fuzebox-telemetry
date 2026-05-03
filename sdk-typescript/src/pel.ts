/**
 * Public openPelRow context wrapper. Mirrors the Python `with` semantics.
 */

import { fuzebox } from './client.js';

export interface PelRow {
  rowId: string;
  tenantId: string;
  skill: string;
  caseId: string;
  status: string;
  trustLevel: number;
  setPredictedOutcomeUsd(value: number | string): void;
  setActualOutcomeUsd(value: number | string): void;
  addMeta(key: string, value: unknown): void;
}

export interface OpenPelRowArgs {
  skill: string;
  caseId?: string;
  agentId?: string;
  model?: string;
  costUsd?: number | string;
  meta?: Record<string, unknown>;
}

class PelRowImpl implements PelRow {
  rowId: string;
  tenantId: string;
  skill: string;
  caseId: string;
  status: string;
  trustLevel: number;

  private predicted: string | undefined;
  private actual: string | undefined;
  private extra: Record<string, unknown> = {};

  constructor(opened: {
    row_id: string;
    tenant_id: string;
    skill: string;
    case_id: string;
    status: string;
    trust_level: number;
  }) {
    this.rowId = opened.row_id;
    this.tenantId = opened.tenant_id;
    this.skill = opened.skill;
    this.caseId = opened.case_id;
    this.status = opened.status;
    this.trustLevel = opened.trust_level;
  }

  setPredictedOutcomeUsd(value: number | string): void {
    this.predicted = String(value);
  }

  setActualOutcomeUsd(value: number | string): void {
    this.actual = String(value);
  }

  addMeta(key: string, value: unknown): void {
    this.extra[key] = value;
  }

  closePayload(): {
    extra_meta: Record<string, unknown>;
    predicted_outcome_usd?: string;
    actual_outcome_usd?: string;
  } {
    const out: {
      extra_meta: Record<string, unknown>;
      predicted_outcome_usd?: string;
      actual_outcome_usd?: string;
    } = { extra_meta: this.extra };
    if (this.predicted !== undefined) out.predicted_outcome_usd = this.predicted;
    if (this.actual !== undefined) out.actual_outcome_usd = this.actual;
    return out;
  }
}

/**
 * Open a hash-chained, signed PEL row for the duration of `body`.
 *
 * The SDK never throws back into the agent: network failures are swallowed
 * and the row is tagged `unledgered`, identical to the Python SDK.
 */
export async function openPelRow<T>(
  args: OpenPelRowArgs,
  body: (row: PelRow) => Promise<T>,
): Promise<T> {
  const caseId = args.caseId ?? crypto.randomUUID();
  let opened;
  try {
    opened = await fuzebox.openRow({
      agent_id: args.agentId ?? 'default',
      skill: args.skill,
      case_id: caseId,
      model: args.model ?? null,
      cost_usd: String(args.costUsd ?? '0'),
      meta: args.meta ?? {},
    });
  } catch (_err) {
    opened = {
      row_id: crypto.randomUUID(),
      tenant_id: 'unknown',
      agent_id: args.agentId ?? 'default',
      skill: args.skill,
      case_id: caseId,
      status: 'unledgered',
      trust_level: 0,
    };
  }
  const row = new PelRowImpl(opened);
  try {
    return await body(row);
  } finally {
    try {
      await fuzebox.closeRow(row.rowId, row.closePayload());
    } catch (_err) {
      // never propagate
    }
  }
}
