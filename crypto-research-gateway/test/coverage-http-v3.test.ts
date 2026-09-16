import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

const acquisitionContext = {
  sources: [
    { source: 'fx-free', sourceType: 'connector', domains: ['forex'], entitlement: 'VERIFIED_REALTIME', available: true },
  ],
};

function observations() {
  const base = {
    domain: 'forex', symbol: 'EURUSD', source: 'fx-free', sourceType: 'connector', freshness: 'FRESH',
    session: 'london_new_york_overlap', entitlement: 'VERIFIED_REALTIME', delayClass: 'REALTIME',
    instrumentType: 'forex', evidenceKind: 'bar', canonicalSymbol: 'EURUSD', providerSymbol: 'C:EURUSD',
  };
  return [
    { ...base, id: 'ctx', eventTime: '2026-09-16T11:00:00.000Z', ingestTime: '2026-09-16T11:00:01.000Z', timeframe: '1h', open: 1.18, high: 1.184, low: 1.179, close: 1.183, bid: 1.1829, ask: 1.1831 },
    { ...base, id: 'e1', eventTime: '2026-09-16T11:15:00.000Z', ingestTime: '2026-09-16T11:15:01.000Z', timeframe: '15m', open: 1.181, high: 1.185, low: 1.18, close: 1.184, bid: 1.1839, ask: 1.1841 },
    { ...base, id: 'e2', eventTime: '2026-09-16T11:30:00.000Z', ingestTime: '2026-09-16T11:30:01.000Z', timeframe: '15m', open: 1.184, high: 1.187, low: 1.183, close: 1.186, bid: 1.1859, ask: 1.1861 },
    { ...base, id: 'e3', eventTime: '2026-09-16T11:45:00.000Z', ingestTime: '2026-09-16T11:45:01.000Z', timeframe: '15m', open: 1.186, high: 1.19, low: 1.185, close: 1.189, bid: 1.1889, ask: 1.1891 },
  ];
}

describe('V3 autoscan HTTP coverage quality', () => {
  it('reports LIVE only for verified realtime fresh evidence', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T11:50:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { requestedDomains: ['forex'], acquisitionContext, externalObservations: observations() },
    });
    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.coverage[0]).toEqual(expect.objectContaining({
      domain: 'forex', status: 'LIVE', liveObservationCount: 4, contextObservationCount: 0, totalObservationCount: 4,
    }));
    await app.close();
  });

  it('reports CONTEXT_ONLY when V3 entry evidence is stale instead of calling it covered', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T14:00:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { requestedDomains: ['forex'], acquisitionContext, externalObservations: observations() },
    });
    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.coverage[0].status).toBe('CONTEXT_ONLY');
    expect(body.coverage[0].reasons).toContain('NO_LIVE_EVIDENCE');
    expect(body.degraded).toBe(true);
    await app.close();
  });
});
