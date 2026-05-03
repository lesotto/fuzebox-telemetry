/**
 * Smoke tests for the TypeScript SDK using node:test + a mocked global fetch.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { fuzebox, openPelRow } from '../src/index.js';

type FetchCall = { url: string; init: RequestInit };

function mockFetch(handler: (call: FetchCall) => Response | Promise<Response>): () => FetchCall[] {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    const call = { url, init: init ?? {} };
    calls.push(call);
    return await handler(call);
  }) as typeof fetch;
  return () => calls;
}

test('init is idempotent', () => {
  fuzebox.shutdown();
  fuzebox.init({ apiKey: 'k', tenant: 'acme', endpoint: 'http://localhost:8080' });
  fuzebox.init({ apiKey: 'k', tenant: 'acme', endpoint: 'http://localhost:8080' });
});

test('openPelRow happy path posts open and close', async () => {
  fuzebox.shutdown();
  fuzebox.init({ apiKey: 'k', tenant: 'acme', endpoint: 'http://cosigner.test' });

  const calls = mockFetch(async ({ url }) => {
    if (url.endsWith('/v1/pel/open')) {
      return new Response(
        JSON.stringify({
          row_id: 'r1',
          tenant_id: 'acme',
          agent_id: 'default',
          skill: 's',
          case_id: 'c',
          status: 'open',
          trust_level: 1,
        }),
        { status: 201 },
      );
    }
    return new Response(JSON.stringify({ status: 'closed' }), { status: 200 });
  });

  await openPelRow({ skill: 's', caseId: 'c' }, async (row) => {
    assert.equal(row.rowId, 'r1');
    row.setPredictedOutcomeUsd('12.50');
    row.addMeta('stripe_payment_intent_id', 'pi_x');
  });

  const log = calls();
  assert.equal(log.length, 2);
  assert.ok(log[0]!.url.endsWith('/v1/pel/open'));
  assert.ok(log[1]!.url.endsWith('/v1/pel/r1/close'));
  const closeBody = JSON.parse(log[1]!.init.body as string);
  assert.equal(closeBody.predicted_outcome_usd, '12.50');
  assert.equal(closeBody.extra_meta.stripe_payment_intent_id, 'pi_x');
});

test('openPelRow fails open when endpoint unreachable', async () => {
  fuzebox.shutdown();
  fuzebox.init({
    apiKey: 'k',
    tenant: 'acme',
    endpoint: 'http://does-not-exist.invalid',
    timeoutMs: 50,
  });

  globalThis.fetch = (async () => {
    throw new Error('network down');
  }) as typeof fetch;

  let observed = '';
  await openPelRow({ skill: 's' }, async (row) => {
    observed = row.status;
  });
  assert.equal(observed, 'unledgered');
});
