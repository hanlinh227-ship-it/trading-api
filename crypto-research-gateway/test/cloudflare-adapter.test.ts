import { describe, expect, it } from 'vitest';
import { createResearchGatewayHandler } from '../../cloudflare-worker/research-gateway.js';

function fakeRuntime() {
  return {
    getLastProbeAt: () => 1_000,
    getHealth: () => ({
      bybit: { ok: true, checkedAt: 1_000 },
      binance: { ok: true, checkedAt: 1_000 },
    }),
    probeAll: async () => ({
      bybit: { ok: true, checkedAt: 1_000 },
      binance: { ok: true, checkedAt: 1_000 },
    }),
    runMarket: async (input: Record<string, unknown>) => ({
      ok: true,
      degraded: false,
      capability: input.action === 'execution_quote' ? 'market_execution_quote' : 'market_snapshot',
      echo: input,
    }),
  };
}

describe('Cloudflare research gateway adapter', () => {
  it('returns null for unrelated routes so existing trading handlers remain authoritative', async () => {
    const handle = createResearchGatewayHandler({ runtime: fakeRuntime() as never, now: () => 2_000 });
    const response = await handle(new Request('https://worker.test/runtime/contract'), { RUNTIME_REVISION: 'sha-1' });
    expect(response).toBeNull();
  });

  it('reports Cloudflare zero-local health with the exact runtime revision', async () => {
    const handle = createResearchGatewayHandler({ runtime: fakeRuntime() as never, now: () => 2_000 });
    const response = await handle(new Request('https://worker.test/health'), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(200);
    const body = await response?.json() as Record<string, unknown>;
    expect(body.runtimeProvider).toBe('cloudflare-workers');
    expect(body.deploymentSourceSha).toBe('sha-1');
    expect(body.localInstallRequired).toBe(false);
  });

  it('advertises only approved read-only capabilities', async () => {
    const handle = createResearchGatewayHandler({ runtime: fakeRuntime() as never, now: () => 2_000 });
    const response = await handle(new Request('https://worker.test/capabilities'), { RUNTIME_REVISION: 'sha-1' });
    const body = await response?.json() as { tools: string[] };
    expect(body.tools).toContain('market_execution_quote');
    expect(JSON.stringify(body.tools)).not.toMatch(/place_order|cancel_order|withdraw|transfer|swap|bridge|wallet|payment/i);
  });

  it('rejects execution quotes without side before provider execution', async () => {
    const handle = createResearchGatewayHandler({ runtime: fakeRuntime() as never, now: () => 2_000 });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(400);
  });

  it('normalizes and forwards a valid venue-bound execution quote request', async () => {
    const handle = createResearchGatewayHandler({ runtime: fakeRuntime() as never, now: () => 2_000 });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'btcusdt', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(200);
    const body = await response?.json() as { echo: Record<string, unknown> };
    expect(body.echo.symbol).toBe('BTCUSDT');
    expect(body.echo.side).toBe('LONG');
    expect(body.echo.executionVenue).toBe('bybit');
  });
});
