import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

function risingObservations() {
  return [
    {
      id: 'fx-1', domain: 'forex', symbol: 'EURUSD', source: 'massive', sourceType: 'connector',
      eventTime: '2026-09-16T06:00:00.000Z', ingestTime: '2026-09-16T08:00:01.000Z', freshness: 'FRESH', timeframe: '1h',
      open: 1.176, high: 1.18, low: 1.175, close: 1.179, bid: 1.1789, ask: 1.1791,
    },
    {
      id: 'fx-2', domain: 'forex', symbol: 'EURUSD', source: 'massive', sourceType: 'connector',
      eventTime: '2026-09-16T07:00:00.000Z', ingestTime: '2026-09-16T08:00:01.000Z', freshness: 'FRESH', timeframe: '1h',
      open: 1.179, high: 1.183, low: 1.178, close: 1.182, bid: 1.1819, ask: 1.1821,
    },
    {
      id: 'fx-3', domain: 'forex', symbol: 'EURUSD', source: 'massive', sourceType: 'connector',
      eventTime: '2026-09-16T08:00:00.000Z', ingestTime: '2026-09-16T08:00:01.000Z', freshness: 'FRESH', timeframe: '1h',
      open: 1.182, high: 1.186, low: 1.181, close: 1.185, bid: 1.1849, ask: 1.1851,
      chart: { provider: 'tradingview', symbol: 'FX:EURUSD', timeframe: '60', verified: true },
    },
  ];
}

describe('autonomous multi-market research HTTP surface', () => {
  it('turns normalized evidence into a ranked research-only TOP_SETUP', async () => {
    process.env.DEPLOYMENT_SOURCE_SHA = 'autoscan-test-sha';
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        intent: 'tìm lệnh tốt nhất',
        requestedDomains: ['forex'],
        externalObservations: risingObservations(),
        maxResults: 1,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.researchOnly).toBe(true);
    expect(body.productionExecutionAuthority).toBe(false);
    expect(body.capability).toBe('autonomous_multi_market_research');
    expect(body.scope).toEqual(['forex']);
    expect(body.timeframePlan).toEqual({ context: '1h', entry: '15m', fast: '5m' });
    expect(body.coverage).toEqual([{ domain: 'forex', requested: true, usableObservationCount: 3, status: 'COVERED', reasons: [] }]);
    expect(body.candidatesBuilt).toBe(1);
    expect(body.decision).toBe('TOP_SETUP');
    expect(body.ranked).toHaveLength(1);
    expect(body.ranked[0].symbol).toBe('EURUSD');
    expect(body.ranked[0].chartContext.mappingStatus).toBe('VERIFIED');
    expect(body.dataContract.kind).toBe('autonomous_multi_market_research');
    expect(body.dataContract.source_sha).toBe('autoscan-test-sha');
    await app.close();
    delete process.env.DEPLOYMENT_SOURCE_SHA;
  });

  it('reports coverage gaps instead of fabricating missing markets', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        requestedDomains: ['forex', 'metals'],
        externalObservations: risingObservations(),
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.coverage).toEqual([
      { domain: 'forex', requested: true, usableObservationCount: 3, status: 'COVERED', reasons: [] },
      { domain: 'metals', requested: true, usableObservationCount: 0, status: 'GAP', reasons: ['NO_USABLE_EVIDENCE'] },
    ]);
    expect(body.degraded).toBe(true);
    expect(body.decision).toBe('TOP_SETUP');
    await app.close();
  });

  it('returns NO_TRADE when available evidence is stale', async () => {
    const app = buildApp({ probeOnStart: false });
    const stale = risingObservations().map((item) => ({ ...item, freshness: 'STALE' }));
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { requestedDomains: ['forex'], externalObservations: stale },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.decision).toBe('NO_TRADE');
    expect(body.ranked).toEqual([]);
    expect(body.coverage[0].status).toBe('GAP');
    expect(body.coverage[0].reasons).toContain('NO_FRESH_EVIDENCE');
    expect(body.blocked[0].reasons).toContain('STALE_OR_UNKNOWN_EVIDENCE');
    await app.close();
  });

  it('rejects write or execution directives', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { requestedDomains: ['forex'], externalObservations: risingObservations(), placeOrder: true },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json().error).toBe('invalid_autoscan_request');
    await app.close();
  });

  it('rejects malformed OHLC evidence before candidate construction', async () => {
    const app = buildApp({ probeOnStart: false });
    const malformed = risingObservations();
    malformed[2] = { ...malformed[2], high: 1.17 };
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { requestedDomains: ['forex'], externalObservations: malformed },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json().error).toBe('invalid_autoscan_observation');
    await app.close();
  });
});
