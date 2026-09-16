import { describe, expect, it } from 'vitest';
import {
  buildCandidateFromObservations,
  buildCandidatesFromObservations,
  buildTimeframePlan,
  groupObservations,
  validateObservationSemantics,
  type NormalizedMarketObservation,
} from '../src/intelligence/autonomous-scan.js';

function obs(overrides: Partial<NormalizedMarketObservation> = {}): NormalizedMarketObservation {
  return {
    id: 'eurusd-1h-1',
    domain: 'forex',
    symbol: 'EURUSD',
    source: 'massive',
    sourceType: 'connector',
    eventTime: '2026-09-16T08:00:00.000Z',
    ingestTime: '2026-09-16T08:00:01.000Z',
    freshness: 'FRESH',
    timeframe: '1h',
    open: 1.18,
    high: 1.185,
    low: 1.178,
    close: 1.183,
    bid: 1.1829,
    ask: 1.1831,
    ...overrides,
  };
}

function risingBars(): NormalizedMarketObservation[] {
  return [
    obs({ id: 'r1', eventTime: '2026-09-16T06:00:00.000Z', open: 1.176, high: 1.18, low: 1.175, close: 1.179, bid: 1.1789, ask: 1.1791 }),
    obs({ id: 'r2', eventTime: '2026-09-16T07:00:00.000Z', open: 1.179, high: 1.183, low: 1.178, close: 1.182, bid: 1.1819, ask: 1.1821 }),
    obs({ id: 'r3', eventTime: '2026-09-16T08:00:00.000Z', open: 1.182, high: 1.186, low: 1.181, close: 1.185, bid: 1.1849, ask: 1.1851 }),
  ];
}

function fallingBars(): NormalizedMarketObservation[] {
  return [
    obs({ id: 'f1', eventTime: '2026-09-16T06:00:00.000Z', open: 1.19, high: 1.191, low: 1.186, close: 1.187, bid: 1.1869, ask: 1.1871 }),
    obs({ id: 'f2', eventTime: '2026-09-16T07:00:00.000Z', open: 1.187, high: 1.188, low: 1.183, close: 1.184, bid: 1.1839, ask: 1.1841 }),
    obs({ id: 'f3', eventTime: '2026-09-16T08:00:00.000Z', open: 1.184, high: 1.185, low: 1.18, close: 1.181, bid: 1.1809, ask: 1.1811 }),
  ];
}

describe('autonomous research planning', () => {
  it('builds a deterministic research-first timeframe plan without caller micromanagement', () => {
    expect(buildTimeframePlan()).toEqual({ context: '1h', entry: '15m', fast: '5m' });
  });
});

describe('normalized observation semantics', () => {
  it('accepts finite OHLC and a non-inverted spread', () => {
    expect(validateObservationSemantics(obs())).toEqual([]);
  });

  it('rejects impossible OHLC geometry', () => {
    const reasons = validateObservationSemantics(obs({ high: 1.17 }));
    expect(reasons).toContain('INVALID_OHLC');
  });

  it('rejects inverted bid ask semantics', () => {
    const reasons = validateObservationSemantics(obs({ bid: 1.184, ask: 1.183 }));
    expect(reasons).toContain('INVALID_SPREAD');
  });

  it('rejects non-finite prices', () => {
    const reasons = validateObservationSemantics(obs({ close: Number.NaN }));
    expect(reasons).toContain('NON_FINITE_PRICE');
  });
});

describe('observation grouping', () => {
  it('groups evidence by domain and symbol without mixing markets', () => {
    const grouped = groupObservations([
      obs({ id: 'fx-a' }),
      obs({ id: 'fx-b', timeframe: '15m' }),
      obs({ id: 'gold-a', domain: 'metals', symbol: 'XAUUSD', open: 3700, high: 3720, low: 3690, close: 3710, bid: 3709.8, ask: 3710.2 }),
    ]);

    expect([...grouped.keys()]).toEqual(['forex:EURUSD', 'metals:XAUUSD']);
    expect(grouped.get('forex:EURUSD')?.map((item) => item.id)).toEqual(['fx-a', 'fx-b']);
    expect(grouped.get('metals:XAUUSD')?.map((item) => item.id)).toEqual(['gold-a']);
  });
});

describe('research-only candidate builder', () => {
  it('builds a LONG candidate from fresh rising structure', () => {
    const result = buildCandidateFromObservations('forex', 'EURUSD', risingBars());
    expect(result.blockedReasons).toEqual([]);
    expect(result.candidate?.direction).toBe('LONG');
    expect(result.candidate?.freshness).toBe('FRESH');
    expect(result.candidate?.invalidation).toContain('structure_below_');
    expect(result.candidate?.provenance).toEqual(['connector:massive']);
  });

  it('builds a SHORT candidate from fresh falling structure', () => {
    const result = buildCandidateFromObservations('forex', 'EURUSD', fallingBars());
    expect(result.blockedReasons).toEqual([]);
    expect(result.candidate?.direction).toBe('SHORT');
    expect(result.candidate?.invalidation).toContain('structure_above_');
  });

  it('fails closed on stale evidence', () => {
    const bars = risingBars().map((item) => ({ ...item, freshness: 'STALE' as const }));
    const result = buildCandidateFromObservations('forex', 'EURUSD', bars);
    expect(result.candidate).toBeUndefined();
    expect(result.blockedReasons).toContain('STALE_OR_UNKNOWN_EVIDENCE');
  });

  it('requires at least three valid observations on one timeframe', () => {
    const result = buildCandidateFromObservations('forex', 'EURUSD', risingBars().slice(0, 2));
    expect(result.candidate).toBeUndefined();
    expect(result.blockedReasons).toContain('INSUFFICIENT_STRUCTURE_EVIDENCE');
  });

  it('blocks ambiguous structure instead of forcing a direction', () => {
    const bars = risingBars();
    bars[1] = { ...bars[1], close: 1.1755, low: 1.1745, open: 1.179, high: 1.18, bid: 1.1754, ask: 1.1756 };
    const result = buildCandidateFromObservations('forex', 'EURUSD', bars);
    expect(result.candidate).toBeUndefined();
    expect(result.blockedReasons).toContain('AMBIGUOUS_STRUCTURE');
  });

  it('builds candidates independently per domain and symbol', () => {
    const gold = risingBars().map((item, index) => ({
      ...item,
      id: `g${index}`,
      domain: 'metals' as const,
      symbol: 'XAUUSD',
      source: 'connector-gold',
      open: 3700 + index * 5,
      high: 3710 + index * 5,
      low: 3695 + index * 5,
      close: 3708 + index * 5,
      bid: 3707.8 + index * 5,
      ask: 3708.2 + index * 5,
    }));
    const result = buildCandidatesFromObservations([...risingBars(), ...gold]);
    expect(result.candidates.map((item) => `${item.domain}:${item.symbol}`)).toEqual(['forex:EURUSD', 'metals:XAUUSD']);
    expect(result.blocked).toEqual([]);
  });
});
