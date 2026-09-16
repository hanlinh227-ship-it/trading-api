import { describe, expect, it } from 'vitest';
import {
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
