import { describe, expect, it } from 'vitest';
import { evaluateDomainEvidence, type NormalizedMarketObservation } from '../src/intelligence/autonomous-scan.js';

const NOW = Date.parse('2026-09-16T12:00:00.000Z');

function v3Obs(overrides: Partial<NormalizedMarketObservation> = {}): NormalizedMarketObservation {
  return {
    id: 'fx-base',
    domain: 'forex',
    symbol: 'EURUSD',
    source: 'connector-test',
    sourceType: 'connector',
    eventTime: '2026-09-16T11:55:00.000Z',
    ingestTime: '2026-09-16T11:55:01.000Z',
    freshness: 'FRESH',
    timeframe: '15m',
    open: 1.18,
    high: 1.185,
    low: 1.178,
    close: 1.183,
    bid: 1.1829,
    ask: 1.1831,
    session: 'london_new_york_overlap',
    entitlement: 'VERIFIED_REALTIME',
    delayClass: 'REALTIME',
    instrumentType: 'forex',
    evidenceKind: 'bar',
    ...overrides,
  };
}

function bars(timeframe: '1h' | '15m', prefix: string): NormalizedMarketObservation[] {
  const contextHours = ['09', '10', '11'];
  return [0, 1, 2].map((index) => v3Obs({
    id: `${prefix}-${index}`,
    timeframe,
    eventTime: timeframe === '1h'
      ? `2026-09-16T${contextHours[index]}:00:00.000Z`
      : `2026-09-16T11:${String(15 + index * 15).padStart(2, '0')}:00.000Z`,
    ingestTime: timeframe === '1h'
      ? `2026-09-16T${contextHours[index]}:00:01.000Z`
      : `2026-09-16T11:${String(15 + index * 15).padStart(2, '0')}:01.000Z`,
    open: 1.18 + index * 0.001,
    high: 1.184 + index * 0.001,
    low: 1.179 + index * 0.001,
    close: 1.183 + index * 0.001,
    bid: 1.1829 + index * 0.001,
    ask: 1.1831 + index * 0.001,
  }));
}

describe('V3 domain evidence enforcement', () => {
  it('does not treat three 15m forex bars as a substitute for 1h context', () => {
    const result = evaluateDomainEvidence('forex', bars('15m', 'entry'), NOW);
    expect(result.eligible).toBe(false);
    expect(result.reasons).toContain('MISSING_CONTEXT_TIMEFRAME');
  });

  it('accepts distinct 1h context and 15m entry bundles with verified realtime semantics', () => {
    const result = evaluateDomainEvidence('forex', [
      ...bars('1h', 'context'),
      ...bars('15m', 'entry'),
    ], NOW);
    expect(result.eligible).toBe(true);
    expect(result.reasons).toEqual([]);
    expect(result.qualitySummary.liveEligible).toBe(6);
  });

  it('requires session context for forex V3 evidence', () => {
    const observations = [...bars('1h', 'context'), ...bars('15m', 'entry')]
      .map((item) => ({ ...item, session: undefined }));
    const result = evaluateDomainEvidence('forex', observations, NOW);
    expect(result.eligible).toBe(false);
    expect(result.reasons).toContain('MISSING_SESSION_CONTEXT');
  });

  it('blocks futures evidence without a resolved current contract', () => {
    const observations = [...bars('1h', 'context'), ...bars('15m', 'entry')].map((item) => ({
      ...item,
      domain: 'futures' as const,
      symbol: 'NQ',
      instrumentType: 'future' as const,
      providerSymbol: undefined,
      contractExpiry: undefined,
    }));
    const result = evaluateDomainEvidence('futures', observations, NOW);
    expect(result.eligible).toBe(false);
    expect(result.reasons).toContain('CONTRACT_UNRESOLVED');
  });

  it('accepts futures evidence only when contract metadata is current and consistent', () => {
    const observations = [...bars('1h', 'context'), ...bars('15m', 'entry')].map((item) => ({
      ...item,
      domain: 'futures' as const,
      symbol: 'NQ',
      instrumentType: 'future' as const,
      providerSymbol: 'NQU26',
      canonicalSymbol: 'NQ',
      contractExpiry: '2026-09-18T21:00:00.000Z',
    }));
    const result = evaluateDomainEvidence('futures', observations, NOW);
    expect(result.eligible).toBe(true);
    expect(result.reasons).toEqual([]);
  });
});
