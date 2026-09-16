import { describe, expect, it } from 'vitest';
import {
  ALL_MARKET_DOMAINS,
  buildChartContext,
  challengeCandidate,
  getMarketProfile,
  normalizeOpportunityScore,
  rankOpportunities,
  resolveMarketScope,
  type OpportunityCandidate,
} from '../src/intelligence/multi-market.js';

function candidate(overrides: Partial<OpportunityCandidate> = {}): OpportunityCandidate {
  return {
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
      { id: 'flow', direction: 'LONG', strength: 0.6, freshness: 'FRESH', source: 'flow-engine' },
      { id: 'counter', direction: 'SHORT', strength: 0.2, freshness: 'FRESH', source: 'challenge-engine' },
    ],
    ...overrides,
  };
}

describe('multi-market scope and profiles', () => {
  it('defaults to all approved research domains without creating a second router', () => {
    expect(resolveMarketScope()).toEqual(ALL_MARKET_DOMAINS);
    expect(ALL_MARKET_DOMAINS).toEqual([
      'crypto',
      'forex',
      'futures',
      'indices',
      'metals',
      'commodities',
    ]);
  });

  it('deduplicates an explicit bounded scope while preserving request order', () => {
    expect(resolveMarketScope(['metals', 'crypto', 'metals', 'forex'])).toEqual(['metals', 'crypto', 'forex']);
  });

  it.each(ALL_MARKET_DOMAINS)('%s profile is research-only and cannot grant execution authority', (domain) => {
    const profile = getMarketProfile(domain);
    expect(profile.domain).toBe(domain);
    expect(profile.researchOnly).toBe(true);
    expect(profile.productionExecutionAuthority).toBe(false);
    expect(profile.requiredEvidence.length).toBeGreaterThan(0);
  });
});

describe('candidate challenge gate', () => {
  it('passes a fresh candidate when aligned evidence dominates the challenge evidence', () => {
    expect(challengeCandidate(candidate())).toEqual({ status: 'PASS', reasons: [] });
  });

  it.each(['STALE', 'UNKNOWN'] as const)('fails closed when candidate freshness is %s', (freshness) => {
    const result = challengeCandidate(candidate({ freshness }));
    expect(result.status).toBe('NO_TRADE');
    expect(result.reasons).toContain('FRESHNESS_INSUFFICIENT');
  });

  it('fails closed on material data conflicts', () => {
    const result = challengeCandidate(candidate({ dataConflict: true }));
    expect(result.status).toBe('NO_TRADE');
    expect(result.reasons).toContain('DATA_CONFLICT');
  });

  it('fails closed when invalidation is missing', () => {
    const result = challengeCandidate(candidate({ invalidation: undefined }));
    expect(result.status).toBe('NO_TRADE');
    expect(result.reasons).toContain('INVALIDATION_REQUIRED');
  });

  it('fails closed when opposing evidence is at least as strong as aligned evidence', () => {
    const result = challengeCandidate(candidate({
      evidence: [
        { id: 'aligned', direction: 'LONG', strength: 0.5, freshness: 'FRESH', source: 'a' },
        { id: 'opposing', direction: 'SHORT', strength: 0.5, freshness: 'FRESH', source: 'b' },
      ],
    }));
    expect(result.status).toBe('NO_TRADE');
    expect(result.reasons).toContain('UNRESOLVED_CONTRADICTION');
  });

  it('fails closed on explicit no-trade evidence', () => {
    const result = challengeCandidate(candidate({
      evidence: [
        ...candidate().evidence,
        { id: 'risk-event', direction: 'NO_TRADE', strength: 1, freshness: 'FRESH', source: 'risk-gate' },
      ],
    }));
    expect(result.status).toBe('NO_TRADE');
    expect(result.reasons).toContain('NO_TRADE_EVIDENCE');
  });
});

describe('cross-market normalization and ranking', () => {
  it('normalizes heterogeneous score scales to a bounded 0-100 score without domain weights', () => {
    expect(normalizeOpportunityScore(8, { min: 0, max: 10 })).toBe(80);
    expect(normalizeOpportunityScore(160, { min: 0, max: 200 })).toBe(80);
    expect(normalizeOpportunityScore(20, { min: 20, max: 20 })).toBe(0);
    expect(normalizeOpportunityScore(999, { min: 0, max: 10 })).toBe(100);
  });

  it('ranks only candidates that pass the challenge gate', () => {
    const result = rankOpportunities([
      candidate({ id: 'crypto', rawScore: 8, scoreScale: { min: 0, max: 10 }, confidence: 0.8 }),
      candidate({ id: 'forex', domain: 'forex', symbol: 'EURUSD', rawScore: 90, scoreScale: { min: 0, max: 100 }, confidence: 0.7, provenance: ['provider:fx'] }),
      candidate({ id: 'blocked', domain: 'metals', symbol: 'XAUUSD', rawScore: 100, scoreScale: { min: 0, max: 100 }, dataConflict: true, provenance: ['provider:metals'] }),
    ]);

    expect(result.decision).toBe('TOP_SETUP');
    expect(result.ranked.map((item) => item.id)).toEqual(['forex', 'crypto']);
    expect(result.blocked).toEqual([{ id: 'blocked', reasons: ['DATA_CONFLICT'] }]);
  });

  it('returns NO_TRADE when every candidate fails the challenge gate', () => {
    const result = rankOpportunities([
      candidate({ id: 'stale', freshness: 'STALE' }),
      candidate({ id: 'conflict', dataConflict: true }),
    ]);
    expect(result.decision).toBe('NO_TRADE');
    expect(result.ranked).toEqual([]);
  });

  it('uses deterministic tie-breaks after normalized score', () => {
    const result = rankOpportunities([
      candidate({ id: 'b', symbol: 'BBB', rawScore: 8, confidence: 0.8, riskReward: 2.1 }),
      candidate({ id: 'a', symbol: 'AAA', rawScore: 8, confidence: 0.8, riskReward: 2.1 }),
      candidate({ id: 'c', symbol: 'CCC', rawScore: 8, confidence: 0.9, riskReward: 1.5 }),
    ]);
    expect(result.ranked.map((item) => item.id)).toEqual(['c', 'a', 'b']);
  });
});

describe('chart context', () => {
  it('preserves an externally verified TradingView symbol without remapping it', () => {
    expect(buildChartContext(candidate({
      chart: { provider: 'tradingview', symbol: 'BYBIT:BTCUSDT.P', timeframe: '15', verified: true },
    }))).toEqual({
      provider: 'tradingview',
      requestedSymbol: 'BTCUSDT',
      symbol: 'BYBIT:BTCUSDT.P',
      timeframe: '15',
      mappingStatus: 'VERIFIED',
    });
  });

  it('does not invent a TradingView/exchange mapping when no verified mapping was supplied', () => {
    expect(buildChartContext(candidate({ chart: undefined }))).toEqual({
      provider: 'tradingview',
      requestedSymbol: 'BTCUSDT',
      symbol: null,
      timeframe: null,
      mappingStatus: 'UNVERIFIED',
    });
  });
});
