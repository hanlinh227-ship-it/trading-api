import { describe, expect, it } from 'vitest';
import { classifyEvidenceQuality } from '../src/intelligence/evidence-quality.js';
import { resolveCurrentContract } from '../src/intelligence/contract-resolver.js';
import { DEFAULT_MARKET_UNIVERSE, resolveUniverse } from '../src/intelligence/market-universe.js';
import { buildDataAcquisitionPlan } from '../src/intelligence/source-planner.js';
import type { NormalizedMarketObservation } from '../src/intelligence/autonomous-scan.js';

function qualityObs(overrides: Partial<NormalizedMarketObservation> = {}): NormalizedMarketObservation {
  return {
    id: 'eurusd-quality',
    domain: 'forex',
    symbol: 'EURUSD',
    source: 'connector-test',
    sourceType: 'connector',
    eventTime: '2026-09-16T12:00:00.000Z',
    ingestTime: '2026-09-16T12:00:01.000Z',
    freshness: 'FRESH',
    timeframe: '15m',
    open: 1.18,
    high: 1.185,
    low: 1.178,
    close: 1.183,
    bid: 1.1829,
    ask: 1.1831,
    entitlement: 'VERIFIED_REALTIME',
    delayClass: 'REALTIME',
    ...overrides,
  };
}

describe('live multi-market V3 market universe', () => {
  it('contains bounded intent-level coverage for all six research domains', () => {
    const domains = new Set(DEFAULT_MARKET_UNIVERSE.map((entry) => entry.domain));
    expect(domains).toEqual(new Set(['crypto', 'forex', 'futures', 'indices', 'metals', 'commodities']));
  });

  it('never guesses an unknown requested symbol', () => {
    const resolved = resolveUniverse(['futures'], { futures: ['MADEUP'] });
    expect(resolved.entries).toEqual([]);
    expect(resolved.unresolved).toEqual([
      { domain: 'futures', symbol: 'MADEUP', reason: 'UNVERIFIED_SYMBOL' },
    ]);
  });

  it('resolves verified canonical forex symbols without changing execution authority', () => {
    const resolved = resolveUniverse(['forex'], { forex: ['EURUSD', 'GBPJPY'] });
    expect(resolved.unresolved).toEqual([]);
    expect(resolved.entries.map((entry) => entry.canonicalSymbol)).toEqual(['EURUSD', 'GBPJPY']);
    expect(resolved.entries.every((entry) => entry.domain === 'forex')).toBe(true);
  });

  it('keeps futures/metals/commodities as product intents rather than permanent dated contracts', () => {
    for (const symbol of ['NQ', 'ES', 'GC', 'CL']) {
      const entry = DEFAULT_MARKET_UNIVERSE.find((item) => item.canonicalSymbol === symbol);
      expect(entry).toBeDefined();
      expect(entry?.productCode).toBe(symbol);
      for (const mapping of Object.values(entry?.mappings ?? {})) {
        expect(mapping.symbol).not.toMatch(/\d{2}$/);
      }
    }
  });
});

describe('live multi-market V3 source planner', () => {
  it('plans all six domains for a broad scan without inventing provider coverage', () => {
    const plan = buildDataAcquisitionPlan({
      capabilities: [
        {
          source: 'crypto-gateway',
          sourceType: 'gateway',
          domains: ['crypto'],
          entitlement: 'VERIFIED_REALTIME',
          available: true,
        },
        {
          source: 'massive',
          sourceType: 'connector',
          domains: ['forex', 'futures', 'indices', 'metals', 'commodities'],
          entitlement: 'NOT_ENTITLED',
          available: true,
        },
      ],
    });

    expect(plan.requestedDomains).toEqual(['crypto', 'forex', 'futures', 'indices', 'metals', 'commodities']);
    expect(plan.sourcesByDomain.crypto).toEqual(['crypto-gateway']);
    expect(plan.gaps).toEqual(expect.arrayContaining([
      { domain: 'forex', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'futures', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'indices', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'metals', reason: 'NO_ENTITLED_SOURCE' },
      { domain: 'commodities', reason: 'NO_ENTITLED_SOURCE' },
    ]));
    expect(plan.researchOnly).toBe(true);
    expect(plan.productionExecutionAuthority).toBe(false);
  });

  it('uses an available verified source only for domains that source actually covers', () => {
    const plan = buildDataAcquisitionPlan({
      requestedDomains: ['forex', 'indices'],
      capabilities: [
        {
          source: 'fx-free',
          sourceType: 'connector',
          domains: ['forex'],
          entitlement: 'VERIFIED_REALTIME',
          available: true,
        },
      ],
    });

    expect(plan.sourcesByDomain.forex).toEqual(['fx-free']);
    expect(plan.sourcesByDomain.indices).toBeUndefined();
    expect(plan.gaps).toContainEqual({ domain: 'indices', reason: 'NO_AVAILABLE_SOURCE' });
  });

  it('treats delayed entitlement as context-only and not an entitled live source', () => {
    const plan = buildDataAcquisitionPlan({
      requestedDomains: ['forex'],
      capabilities: [
        {
          source: 'delayed-fx',
          sourceType: 'connector',
          domains: ['forex'],
          entitlement: 'VERIFIED_DELAYED',
          available: true,
        },
      ],
    });

    expect(plan.sourcesByDomain.forex).toBeUndefined();
    expect(plan.gaps).toContainEqual({ domain: 'forex', reason: 'NO_ENTITLED_SOURCE' });
    expect(plan.entitlementStateBySource['delayed-fx']).toBe('VERIFIED_DELAYED');
  });
});

describe('live multi-market V3 evidence quality', () => {
  const clock = {
    nowMs: Date.parse('2026-09-16T12:00:02.000Z'),
    maxAgeMs: 10_000,
    clockSkewMs: 2_000,
  };

  it('allows verified realtime evidence when event time is fresh', () => {
    const q = classifyEvidenceQuality(qualityObs(), clock);
    expect(q).toEqual({ liveEligible: true, state: 'LIVE_REALTIME', reasons: [] });
  });

  it('blocks delayed evidence from live eligibility even when event time is recent', () => {
    const q = classifyEvidenceQuality(qualityObs({
      entitlement: 'VERIFIED_DELAYED',
      delayClass: 'DELAYED',
    }), clock);
    expect(q.liveEligible).toBe(false);
    expect(q.state).toBe('DELAYED_CONTEXT');
    expect(q.reasons).toContain('DELAYED_ENTITLEMENT');
  });

  it('blocks connector evidence when entitlement is unknown', () => {
    const q = classifyEvidenceQuality(qualityObs({ entitlement: 'UNVERIFIED', delayClass: 'UNKNOWN' }), clock);
    expect(q.liveEligible).toBe(false);
    expect(q.state).toBe('UNKNOWN');
    expect(q.reasons).toContain('ENTITLEMENT_UNVERIFIED');
  });

  it('rejects future event timestamps beyond skew tolerance', () => {
    const q = classifyEvidenceQuality(qualityObs({
      eventTime: '2026-09-16T12:01:00.000Z',
      ingestTime: '2026-09-16T12:01:01.000Z',
    }), clock);
    expect(q.state).toBe('INVALID');
    expect(q.reasons).toContain('EVENT_TIME_IN_FUTURE');
  });

  it('rejects ingest timestamps materially before event timestamps', () => {
    const q = classifyEvidenceQuality(qualityObs({
      eventTime: '2026-09-16T12:00:00.000Z',
      ingestTime: '2026-09-16T11:59:50.000Z',
    }), clock);
    expect(q.state).toBe('INVALID');
    expect(q.reasons).toContain('INGEST_BEFORE_EVENT');
  });

  it('classifies an old observation as stale when the market is expected active', () => {
    const q = classifyEvidenceQuality(qualityObs({
      eventTime: '2026-09-16T11:00:00.000Z',
      ingestTime: '2026-09-16T11:00:01.000Z',
    }), clock);
    expect(q.liveEligible).toBe(false);
    expect(q.state).toBe('STALE');
  });

  it('keeps a closed-market last observation as context instead of mislabeling it live', () => {
    const q = classifyEvidenceQuality(qualityObs({
      eventTime: '2026-09-15T20:00:00.000Z',
      ingestTime: '2026-09-15T20:00:01.000Z',
      session: 'closed',
    }), clock);
    expect(q.liveEligible).toBe(false);
    expect(q.state).toBe('DELAYED_CONTEXT');
    expect(q.reasons).toContain('MARKET_CLOSED_CONTEXT');
  });
});

describe('live multi-market V3 futures contract resolution', () => {
  const nowMs = Date.parse('2026-09-16T12:00:00.000Z');

  it('selects the nearest active non-expired verified realtime contract', () => {
    const result = resolveCurrentContract('NQ', [
      { productCode: 'NQ', ticker: 'NQU26', expiry: '2026-09-18T21:00:00Z', active: true, entitlement: 'VERIFIED_REALTIME' },
      { productCode: 'NQ', ticker: 'NQZ26', expiry: '2026-12-18T21:00:00Z', active: true, entitlement: 'VERIFIED_REALTIME' },
    ], nowMs);

    expect(result.status).toBe('RESOLVED');
    if (result.status === 'RESOLVED') expect(result.contract.ticker).toBe('NQU26');
  });

  it('does not select a delayed nearer contract over a verified realtime contract', () => {
    const result = resolveCurrentContract('GC', [
      { productCode: 'GC', ticker: 'GCV26', expiry: '2026-09-28T21:00:00Z', active: true, entitlement: 'VERIFIED_DELAYED' },
      { productCode: 'GC', ticker: 'GCZ26', expiry: '2026-12-28T21:00:00Z', active: true, entitlement: 'VERIFIED_REALTIME' },
    ], nowMs);

    expect(result.status).toBe('RESOLVED');
    if (result.status === 'RESOLVED') expect(result.contract.ticker).toBe('GCZ26');
  });

  it('blocks rather than guessing when no valid contract exists', () => {
    expect(resolveCurrentContract('GC', [], nowMs)).toEqual({ status: 'BLOCKED', reason: 'CONTRACT_UNRESOLVED' });
  });

  it('distinguishes expired evidence from no contract evidence', () => {
    expect(resolveCurrentContract('CL', [
      { productCode: 'CL', ticker: 'CLU26', expiry: '2026-09-10T21:00:00Z', active: true, entitlement: 'VERIFIED_REALTIME' },
    ], nowMs)).toEqual({ status: 'BLOCKED', reason: 'CONTRACT_EXPIRED' });
  });

  it('ignores candidates belonging to another product', () => {
    expect(resolveCurrentContract('ES', [
      { productCode: 'NQ', ticker: 'NQU26', expiry: '2026-09-18T21:00:00Z', active: true, entitlement: 'VERIFIED_REALTIME' },
    ], nowMs)).toEqual({ status: 'BLOCKED', reason: 'CONTRACT_UNRESOLVED' });
  });
});
