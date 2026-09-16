import { describe, expect, it } from 'vitest';
import { buildResearchLevels } from '../src/intelligence/research-levels.js';
import type { NormalizedMarketObservation } from '../src/intelligence/autonomous-scan.js';

function obs(overrides: Partial<NormalizedMarketObservation> = {}): NormalizedMarketObservation {
  return {
    id: 'btc-level',
    domain: 'crypto',
    symbol: 'BTCUSDT',
    source: 'gateway',
    sourceType: 'gateway',
    eventTime: '2026-09-16T12:00:00.000Z',
    ingestTime: '2026-09-16T12:00:00.100Z',
    freshness: 'FRESH',
    timeframe: '15m',
    open: 100,
    high: 102,
    low: 99,
    close: 100.5,
    bid: 100.9,
    ask: 101,
    entitlement: 'VERIFIED_REALTIME',
    delayClass: 'REALTIME',
    instrumentType: 'perpetual',
    evidenceKind: 'quote',
    ...overrides,
  };
}

describe('V3 research Entry/Stop/Target levels', () => {
  it('uses verified executable ask for LONG and computes RR target', () => {
    const result = buildResearchLevels({
      direction: 'LONG',
      observations: [obs()],
      structuralStop: 99,
      riskReward: 2,
      invalidationBasis: '15m_structure_low',
    });
    expect(result.blockedReason).toBeUndefined();
    expect(result.levels).toEqual({
      entry: 101,
      entrySemantic: 'EXECUTABLE_ASK',
      stop: 99,
      target: 105,
      riskReward: 2,
      invalidationBasis: '15m_structure_low',
      researchOnly: true,
    });
  });

  it('uses verified executable bid for SHORT and computes RR target', () => {
    const result = buildResearchLevels({
      direction: 'SHORT',
      observations: [obs({ bid: 99, ask: 99.1, close: 99.05 })],
      structuralStop: 101,
      riskReward: 2,
      invalidationBasis: '15m_structure_high',
    });
    expect(result.levels?.entrySemantic).toBe('EXECUTABLE_BID');
    expect(result.levels?.entry).toBe(99);
    expect(result.levels?.stop).toBe(101);
    expect(result.levels?.target).toBe(95);
  });

  it('labels close as non-executable when quote entitlement is not verified realtime', () => {
    const result = buildResearchLevels({
      direction: 'LONG',
      observations: [obs({ entitlement: 'UNVERIFIED', delayClass: 'UNKNOWN', close: 100.25 })],
      structuralStop: 99,
      riskReward: 2,
      invalidationBasis: 'structure_low',
    });
    expect(result.levels?.entry).toBe(100.25);
    expect(result.levels?.entrySemantic).toBe('REFERENCE_CLOSE');
    expect(result.levels?.researchOnly).toBe(true);
  });

  it('fails closed when LONG stop is not below entry', () => {
    const result = buildResearchLevels({
      direction: 'LONG',
      observations: [obs()],
      structuralStop: 101,
      riskReward: 2,
      invalidationBasis: 'invalid_geometry',
    });
    expect(result.levels).toBeUndefined();
    expect(result.blockedReason).toBe('INVALID_RISK_GEOMETRY');
  });

  it('fails closed when SHORT stop is not above entry', () => {
    const result = buildResearchLevels({
      direction: 'SHORT',
      observations: [obs({ bid: 99 })],
      structuralStop: 98,
      riskReward: 2,
      invalidationBasis: 'invalid_geometry',
    });
    expect(result.levels).toBeUndefined();
    expect(result.blockedReason).toBe('INVALID_RISK_GEOMETRY');
  });

  it('rejects non-finite or non-positive RR inputs', () => {
    expect(buildResearchLevels({
      direction: 'LONG',
      observations: [obs()],
      structuralStop: 99,
      riskReward: 0,
      invalidationBasis: 'bad_rr',
    }).blockedReason).toBe('INVALID_RISK_GEOMETRY');
  });
});
