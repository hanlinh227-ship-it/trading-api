import { describe, expect, it } from 'vitest';
import { buildCoverageReport } from '../src/intelligence/coverage-report.js';
import type { NormalizedMarketObservation } from '../src/intelligence/autonomous-scan.js';

const NOW = Date.parse('2026-09-16T12:00:00.000Z');

function observation(overrides: Partial<NormalizedMarketObservation> = {}): NormalizedMarketObservation {
  return {
    id: 'obs-1',
    domain: 'forex',
    symbol: 'EURUSD',
    source: 'fx-free',
    sourceType: 'connector',
    eventTime: '2026-09-16T11:59:55.000Z',
    ingestTime: '2026-09-16T11:59:56.000Z',
    freshness: 'FRESH',
    timeframe: '15m',
    open: 1.18,
    high: 1.181,
    low: 1.179,
    close: 1.1805,
    bid: 1.1804,
    ask: 1.1806,
    entitlement: 'VERIFIED_REALTIME',
    delayClass: 'REALTIME',
    instrumentType: 'forex',
    session: 'london_new_york_overlap',
    ...overrides,
  };
}

describe('V3 coverage report', () => {
  it('classifies verified fresh realtime evidence as LIVE', () => {
    const report = buildCoverageReport(['forex'], [observation()], [], NOW);
    expect(report).toEqual([
      expect.objectContaining({
        domain: 'forex',
        status: 'LIVE',
        liveObservationCount: 1,
        contextObservationCount: 0,
        totalObservationCount: 1,
        reasons: [],
      }),
    ]);
  });

  it('classifies delayed but recent evidence as CONTEXT_ONLY rather than LIVE', () => {
    const report = buildCoverageReport([
      'forex',
    ], [observation({ entitlement: 'VERIFIED_DELAYED', delayClass: 'DELAYED' })], [], NOW);
    expect(report[0].status).toBe('CONTEXT_ONLY');
    expect(report[0].liveObservationCount).toBe(0);
    expect(report[0].contextObservationCount).toBe(1);
    expect(report[0].reasons).toContain('NO_LIVE_EVIDENCE');
    expect(report[0].entitlements).toEqual(['VERIFIED_DELAYED']);
  });

  it('keeps unverified entitlement out of LIVE coverage', () => {
    const report = buildCoverageReport([
      'forex',
    ], [observation({ entitlement: 'UNVERIFIED', delayClass: 'UNKNOWN' })], [], NOW);
    expect(report[0].status).toBe('CONTEXT_ONLY');
    expect(report[0].reasons).toContain('ENTITLEMENT_UNVERIFIED');
  });

  it('reports a source-plan gap when a requested domain has no observations', () => {
    const report = buildCoverageReport(
      ['metals'],
      [],
      [{ domain: 'metals', reason: 'NO_ENTITLED_SOURCE' }],
      NOW,
    );
    expect(report).toEqual([
      expect.objectContaining({
        domain: 'metals',
        status: 'GAP',
        liveObservationCount: 0,
        contextObservationCount: 0,
        totalObservationCount: 0,
        reasons: ['NO_ENTITLED_SOURCE'],
      }),
    ]);
  });

  it('never lets a fresh response timestamp upgrade stale market data to LIVE', () => {
    const report = buildCoverageReport([
      'forex',
    ], [observation({
      eventTime: '2026-09-16T10:00:00.000Z',
      ingestTime: '2026-09-16T11:59:59.000Z',
    })], [], NOW);
    expect(report[0].status).toBe('CONTEXT_ONLY');
    expect(report[0].reasons).toContain('NO_LIVE_EVIDENCE');
  });
});
