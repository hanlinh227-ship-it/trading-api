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

function degradedRuntime() {
  return {
    getLastProbeAt: () => 1_000,
    getHealth: () => ({
      bybit: { ok: false, checkedAt: 1_000, error: 'provider_bridge_fetch_failed' },
      binance: { ok: true, checkedAt: 1_000 },
    }),
    probeAll: async () => ({}),
    runMarket: async () => ({ ok: false, degraded: true, error: 'provider_bridge_fetch_failed' }),
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

  it('fails over only a degraded Bybit-bound request through the Railway safety path', async () => {
    let fallbackCalls = 0;
    const fallbackFetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      fallbackCalls += 1;
      expect(String(input)).toBe('https://crypto-research-gateway-prod-production.up.railway.app/research/market');
      expect(init?.method).toBe('POST');
      const requestBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
      expect(requestBody.executionVenue).toBe('bybit');
      return new Response(JSON.stringify({
        ok: true,
        degraded: false,
        executionQuote: {
          executionVerified: true,
          status: 'OK',
          venue: 'bybit',
          instrument: 'perpetual',
          side: 'LONG',
          bid: 100,
          ask: 101,
          executablePrice: 101,
          quoteAgeMs: 25,
        },
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    };
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackFetch,
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(200);
    const body = await response?.json() as Record<string, unknown>;
    expect(body.ok).toBe(true);
    expect(body.edgeRuntimeProvider).toBe('cloudflare-workers');
    expect(body.upstreamFallback).toBe('railway');
    expect(fallbackCalls).toBe(1);
  });

  it('rejects a stale Railway safety quote and preserves the degraded response', async () => {
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackFetch: async () => new Response(JSON.stringify({
        ok: true,
        degraded: false,
        executionQuote: {
          executionVerified: true,
          status: 'OK',
          venue: 'bybit',
          instrument: 'perpetual',
          side: 'LONG',
          bid: 100,
          ask: 101,
          executablePrice: 101,
          quoteAgeMs: 5_001,
        },
      }), { status: 200, headers: { 'content-type': 'application/json' } }),
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(503);
    const body = await response?.json() as Record<string, unknown>;
    expect(body.ok).toBe(false);
    expect(body.degraded).toBe(true);
  });

  it('never sends a degraded Binance-bound request to the Railway Bybit fallback', async () => {
    let fallbackCalls = 0;
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackFetch: async () => {
        fallbackCalls += 1;
        return new Response('{}', { status: 500 });
      },
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'binance' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(503);
    expect(fallbackCalls).toBe(0);
  });
});
