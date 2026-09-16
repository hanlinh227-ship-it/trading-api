import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

const validCandidate = {
  id: 'btc-long',
  domain: 'crypto',
  symbol: 'BTCUSDT',
  direction: 'LONG',
  rawScore: 8,
  scoreScale: { min: 0, max: 10 },
  confidence: 0.8,
  riskReward: 2,
  invalidation: 'structure_lost',
  freshness: 'FRESH',
  dataConflict: false,
  provenance: ['provider:bybit'],
  evidence: [
    { id: 'structure', direction: 'LONG', strength: 0.8, freshness: 'FRESH', source: 'structure-engine' },
    { id: 'counter', direction: 'SHORT', strength: 0.2, freshness: 'FRESH', source: 'challenge-engine' },
  ],
  chart: {
    provider: 'tradingview',
    symbol: 'BYBIT:BTCUSDT.P',
    timeframe: '15',
    verified: true,
  },
};

describe('multi-market research HTTP surface', () => {
  it('returns ranked research-only opportunities with the existing provenance envelope', async () => {
    process.env.DEPLOYMENT_SOURCE_SHA = 'test-source-sha';
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/opportunities',
      payload: {
        requestedDomains: ['crypto', 'forex'],
        candidates: [validCandidate],
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.ok).toBe(true);
    expect(body.researchOnly).toBe(true);
    expect(body.productionExecutionAuthority).toBe(false);
    expect(body.scope).toEqual(['crypto', 'forex']);
    expect(body.decision).toBe('TOP_SETUP');
    expect(body.ranked[0].id).toBe('btc-long');
    expect(body.ranked[0].chartContext.mappingStatus).toBe('VERIFIED');
    expect(body.dataContract.kind).toBe('multi_market_research');
    expect(body.dataContract.source_sha).toBe('test-source-sha');
    expect(body.dataContract.research_only).toBe(true);
    expect(body.dataContract.production_execution_authority).toBe(false);
    expect(body.dataContract.authority.execution).toBe('none');
    await app.close();
    delete process.env.DEPLOYMENT_SOURCE_SHA;
  });

  it('returns an explicit NO_TRADE decision instead of forcing a setup', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/opportunities',
      payload: {
        candidates: [{ ...validCandidate, freshness: 'STALE' }],
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.decision).toBe('NO_TRADE');
    expect(body.ranked).toEqual([]);
    expect(body.blocked[0].reasons).toContain('FRESHNESS_INSUFFICIENT');
    await app.close();
  });

  it('rejects execution/write intent fields instead of widening permissions', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/opportunities',
      payload: {
        candidates: [validCandidate],
        placeOrder: true,
      },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json().error).toBe('invalid_opportunity_request');
    await app.close();
  });

  it('rejects invalid score scales and out-of-range evidence strength', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/opportunities',
      payload: {
        candidates: [{
          ...validCandidate,
          scoreScale: { min: 10, max: 0 },
          evidence: [{ id: 'bad', direction: 'LONG', strength: 2, freshness: 'FRESH', source: 'bad-source' }],
        }],
      },
    });

    expect(response.statusCode).toBe(400);
    expect(response.json().error).toBe('invalid_opportunity_request');
    await app.close();
  });
});
