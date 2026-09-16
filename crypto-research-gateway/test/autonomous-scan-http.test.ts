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

function risingV3Observations() {
  const base = {
    domain: 'forex', symbol: 'EURUSD', source: 'fx-free', sourceType: 'connector', freshness: 'FRESH',
    session: 'london_new_york_overlap', entitlement: 'VERIFIED_REALTIME', delayClass: 'REALTIME',
    instrumentType: 'forex', evidenceKind: 'bar', canonicalSymbol: 'EURUSD', providerSymbol: 'C:EURUSD',
  };
  return [
    { ...base, id: 'fx-v3-context', eventTime: '2026-09-16T11:00:00.000Z', ingestTime: '2026-09-16T11:00:01.000Z', timeframe: '1h', open: 1.18, high: 1.184, low: 1.179, close: 1.183, bid: 1.1829, ask: 1.1831 },
    { ...base, id: 'fx-v3-entry-1', eventTime: '2026-09-16T11:15:00.000Z', ingestTime: '2026-09-16T11:15:01.000Z', timeframe: '15m', open: 1.181, high: 1.185, low: 1.18, close: 1.184, bid: 1.1839, ask: 1.1841 },
    { ...base, id: 'fx-v3-entry-2', eventTime: '2026-09-16T11:30:00.000Z', ingestTime: '2026-09-16T11:30:01.000Z', timeframe: '15m', open: 1.184, high: 1.187, low: 1.183, close: 1.186, bid: 1.1859, ask: 1.1861 },
    { ...base, id: 'fx-v3-entry-3', eventTime: '2026-09-16T11:45:00.000Z', ingestTime: '2026-09-16T11:45:01.000Z', timeframe: '15m', open: 1.186, high: 1.19, low: 1.185, close: 1.189, bid: 1.1889, ask: 1.1891, chart: { provider: 'tradingview', symbol: 'FX:EURUSD', timeframe: '15', verified: true } },
  ];
}

const verifiedFxAcquisitionContext = {
  sources: [
    { source: 'fx-free', sourceType: 'connector', domains: ['forex'], entitlement: 'VERIFIED_REALTIME', available: true },
  ],
};

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

  it('returns capabilityVersion 3 and source gaps without fabricating connector calls', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        intent: 'quét đa thị trường',
        acquisitionContext: {
          sources: [
            { source: 'massive', sourceType: 'connector', domains: ['forex'], entitlement: 'NOT_ENTITLED', available: true },
          ],
        },
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.capabilityVersion).toBe(3);
    expect(body.dataAcquisitionPlan.gaps).toContainEqual({ domain: 'forex', reason: 'NO_ENTITLED_SOURCE' });
    expect(body.sourceCoverage.forex).toEqual({ sources: [], status: 'GAP' });
    expect(body.entitlementSummary.massive).toBe('NOT_ENTITLED');
    expect(body.researchOnly).toBe(true);
    expect(body.productionExecutionAuthority).toBe(false);
    await app.close();
  });

  it('accepts V3 observation semantics and carries research-only levels into ranking', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T11:50:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        requestedDomains: ['forex'],
        acquisitionContext: verifiedFxAcquisitionContext,
        externalObservations: risingV3Observations(),
        maxResults: 1,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.capabilityVersion).toBe(3);
    expect(body.decision).toBe('TOP_SETUP');
    expect(body.ranked).toHaveLength(1);
    expect(body.ranked[0].levels.entrySemantic).toBe('EXECUTABLE_ASK');
    expect(body.ranked[0].levels.researchOnly).toBe(true);
    expect(body.ranked[0]).not.toHaveProperty('orderPermission');
    await app.close();
  });

  it('uses request-time clock so old V3 observations cannot self-refresh from ingest time', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T14:00:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        requestedDomains: ['forex'],
        acquisitionContext: verifiedFxAcquisitionContext,
        externalObservations: risingV3Observations(),
      },
    });
    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.decision).toBe('NO_TRADE');
    expect(body.ranked).toEqual([]);
    expect(body.blocked[0].reasons).toContain('NO_LIVE_EVIDENCE');
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

  it.each(['apiKey', 'token', 'quantity', 'leverage', 'placeOrder'])('rejects forbidden autoscan field %s', async (field) => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { [field]: field === 'placeOrder' ? true : 'x' },
    });
    expect(response.statusCode).toBe(400);
    expect(response.json().error).toBe('invalid_autoscan_request');
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
