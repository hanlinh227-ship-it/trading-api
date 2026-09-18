import { describe, expect, it } from 'vitest';
import { createResearchGatewayHandler } from '../../cloudflare-worker/research-gateway.js';
import { buildDataEnvelope, validateDataEnvelope } from '../src/normalization/data-contract.js';

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

const SECONDARY_URL = 'https://secondary.example';

function withSecondaryContract(raw: Record<string, unknown>) {
  const dataContract = buildDataEnvelope({
    kind: 'crypto_market_research',
    source: 'crypto-research-gateway',
    sourceSha: 'secondary-sha',
    eventTime: '2026-09-13T17:30:00.000Z',
    ingestTime: '2026-09-13T17:30:00.100Z',
    freshness: raw.degraded === true ? 'DEGRADED' : 'FRESH',
    payload: raw,
    provenance: { providers: ['bybit'] },
  });
  return { ...raw, dataContract };
}

function goodFallbackQuote(overrides: Record<string, unknown> = {}) {
  return withSecondaryContract({
    ok: true,
    degraded: false,
    executionQuote: {
      executionVerified: true,
      status: 'OK',
      venue: 'bybit',
      instrumentType: 'perpetual',
      side: 'LONG',
      bid: 100,
      ask: 101,
      executablePrice: 101,
      quoteAgeMs: 25,
      ...overrides,
    },
  });
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

  it('normalizes and forwards a valid request with a verified edge contract', async () => {
    const handle = createResearchGatewayHandler({ runtime: fakeRuntime() as never, now: () => 2_000 });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'btcusdt', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(200);
    const body = await response?.json() as Record<string, any>;
    expect(body.echo.symbol).toBe('BTCUSDT');
    expect(body.echo.side).toBe('LONG');
    expect(body.echo.executionVenue).toBe('bybit');
    expect(validateDataEnvelope(body.dataContract)).toEqual([]);
    expect(body.dataContract.production_execution_authority).toBe(false);
  });

  it('fails over a degraded Bybit request only when the secondary gateway supplies a valid contract', async () => {
    let fallbackCalls = 0;
    const fallbackFetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      fallbackCalls += 1;
      expect(String(input)).toBe('https://secondary.example/research/market');
      expect(init?.method).toBe('POST');
      const requestBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
      expect(requestBody.executionVenue).toBe('bybit');
      return new Response(JSON.stringify(goodFallbackQuote()), { status: 200, headers: { 'content-type': 'application/json' } });
    };
    const handle = createResearchGatewayHandler({ runtime: degradedRuntime() as never, now: () => 2_000, fallbackFetch, fallbackGatewayUrl: SECONDARY_URL });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(200);
    const body = await response?.json() as Record<string, any>;
    expect(body.ok).toBe(true);
    expect(body.edgeRuntimeProvider).toBe('cloudflare-workers');
    expect(body.upstreamFallback).toBe('secondary-research-gateway');
    expect(body.upstreamDataContract.payload_hash).toBeTruthy();
    expect(validateDataEnvelope(body.dataContract)).toEqual([]);
    expect(fallbackCalls).toBe(1);
  });

  it('rejects a secondary fallback response with no data contract', async () => {
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackGatewayUrl: SECONDARY_URL,
      fallbackFetch: async () => new Response(JSON.stringify({
        ok: true,
        degraded: false,
        executionQuote: {
          executionVerified: true,
          status: 'OK',
          venue: 'bybit',
          instrumentType: 'perpetual',
          side: 'LONG',
          bid: 100,
          ask: 101,
          executablePrice: 101,
          quoteAgeMs: 25,
        },
      }), { status: 200, headers: { 'content-type': 'application/json' } }),
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(503);
  });

  it('rejects a fallback quote whose instrumentType does not match the request', async () => {
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackGatewayUrl: SECONDARY_URL,
      fallbackFetch: async () => new Response(JSON.stringify(goodFallbackQuote({ instrumentType: 'spot' })), { status: 200, headers: { 'content-type': 'application/json' } }),
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(response?.status).toBe(503);
  });

  it('rejects a stale secondary safety quote and preserves the degraded response', async () => {
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackGatewayUrl: SECONDARY_URL,
      fallbackFetch: async () => new Response(JSON.stringify(goodFallbackQuote({ quoteAgeMs: 5_001 })), { status: 200, headers: { 'content-type': 'application/json' } }),
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

  it('never sends a degraded Binance-bound request to the secondary Bybit fallback', async () => {
    let fallbackCalls = 0;
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackGatewayUrl: SECONDARY_URL,
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

  it('fails closed when no secondary gateway is configured, rather than reaching for a default', async () => {
    // The hard-coded Railway URL used to live here. Removing it must mean "no
    // fallback", not "some other default": a degraded primary with nowhere
    // verified to go returns the degraded answer truthfully.
    let fallbackCalls = 0;
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackFetch: async () => { fallbackCalls += 1; return new Response('{}', { status: 200 }); },
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(fallbackCalls).toBe(0);
    expect(response?.status).toBe(503);
    const body = await response?.json() as Record<string, unknown>;
    expect(body.ok).toBe(false);
    expect(body.degraded).toBe(true);
    expect(body.upstreamFallback).toBeUndefined();
  });

  it('refuses a retired Railway host even when one is explicitly configured', async () => {
    // A URL is the easiest way for a removed provider to return. Configuring one
    // must not work, whether by accident or by a stale environment variable.
    let fallbackCalls = 0;
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackGatewayUrl: 'https://crypto-research-gateway-prod-production.up.railway.app',
      fallbackFetch: async () => { fallbackCalls += 1; return new Response('{}', { status: 200 }); },
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(fallbackCalls).toBe(0);
    expect(response?.status).toBe(503);
  });

  it('reads the secondary gateway from the environment when one is set', async () => {
    let seen = '';
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackFetch: async (input: RequestInfo | URL) => {
        seen = String(input);
        return new Response(JSON.stringify(goodFallbackQuote()), { status: 200, headers: { 'content-type': 'application/json' } });
      },
    });
    const response = await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1', SECONDARY_RESEARCH_GATEWAY_URL: SECONDARY_URL });
    expect(seen).toBe('https://secondary.example/research/market');
    expect(response?.status).toBe(200);
  });

  it('rejects a non-https secondary gateway', async () => {
    let fallbackCalls = 0;
    const handle = createResearchGatewayHandler({
      runtime: degradedRuntime() as never,
      now: () => 2_000,
      fallbackGatewayUrl: 'http://insecure.example',
      fallbackFetch: async () => { fallbackCalls += 1; return new Response('{}', { status: 200 }); },
    });
    await handle(new Request('https://worker.test/research/market', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'execution_quote', symbol: 'BTCUSDT', instrument: 'perpetual', side: 'LONG', executionVenue: 'bybit' }),
    }), { RUNTIME_REVISION: 'sha-1' });
    expect(fallbackCalls).toBe(0);
  });
});
