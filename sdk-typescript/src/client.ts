/**
 * Cosigner API client + idempotent init.
 */

export interface InitOptions {
  apiKey: string;
  tenant: string;
  endpoint: string;
  timeoutMs?: number;
}

interface OpenPayload {
  agent_id: string;
  skill: string;
  case_id: string;
  model: string | null;
  cost_usd: string;
  meta: Record<string, unknown>;
}

interface OpenResponse {
  row_id: string;
  tenant_id: string;
  agent_id: string;
  skill: string;
  case_id: string;
  status: string;
  trust_level: number;
}

interface ClosePayload {
  predicted_outcome_usd?: string;
  actual_outcome_usd?: string;
  extra_meta: Record<string, unknown>;
}

class Fuzebox {
  private cfg: InitOptions | null = null;

  init(opts: InitOptions): void {
    if (this.cfg && JSON.stringify(this.cfg) === JSON.stringify(opts)) return;
    this.cfg = { timeoutMs: 2000, ...opts };
  }

  shutdown(): void {
    this.cfg = null;
  }

  private requireCfg(): InitOptions {
    if (!this.cfg) throw new Error('fuzebox.init must be called first');
    return this.cfg;
  }

  async openRow(payload: OpenPayload): Promise<OpenResponse> {
    const cfg = this.requireCfg();
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), cfg.timeoutMs ?? 2000);
      try {
        const resp = await fetch(`${cfg.endpoint.replace(/\/$/, '')}/v1/pel/open`, {
          method: 'POST',
          headers: this.headers(cfg),
          body: JSON.stringify(payload),
          signal: ctrl.signal,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return (await resp.json()) as OpenResponse;
      } finally {
        clearTimeout(timer);
      }
    } catch (_err) {
      // Fail-open: synthesize an unledgered stub.
      return {
        row_id: crypto.randomUUID(),
        tenant_id: cfg.tenant,
        agent_id: payload.agent_id,
        skill: payload.skill,
        case_id: payload.case_id,
        status: 'unledgered',
        trust_level: 0,
      };
    }
  }

  async closeRow(rowId: string, payload: ClosePayload): Promise<void> {
    const cfg = this.requireCfg();
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), cfg.timeoutMs ?? 2000);
      try {
        await fetch(`${cfg.endpoint.replace(/\/$/, '')}/v1/pel/${rowId}/close`, {
          method: 'POST',
          headers: this.headers(cfg),
          body: JSON.stringify(payload),
          signal: ctrl.signal,
        });
      } finally {
        clearTimeout(timer);
      }
    } catch (_err) {
      // Swallow — the agent never sees a transport failure.
    }
  }

  private headers(cfg: InitOptions): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${cfg.apiKey}`,
      'X-Tenant-Id': cfg.tenant,
      'User-Agent': 'fuzebox-typescript/0.1',
    };
  }
}

export const fuzebox = new Fuzebox();
