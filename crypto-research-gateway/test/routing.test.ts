import { describe, expect, it } from 'vitest';
import { resolveExecutionVenue, selectProviders } from '../src/routing/capability-router.js';

const healthy = {
  binance: { ok: true, checkedAt: 1 },
  okx: { ok: true, checkedAt: 1 },
  bybit: { ok: true, checkedAt: 1 },
  gate: { ok: true, checkedAt: 1 },
  kucoin: { ok: true, checkedAt: 1 },
};

describe('selectProviders', () => {
  it('returns at most three provider candidates', () => {
    expect(selectProviders({ capability: 'market_snapshot', health: healthy })).toHaveLength(3);
  });

  it('puts an explicitly preferred healthy venue first', () => {
    expect(selectProviders({ capability: 'market_snapshot', preferredVenue: 'gate', health: healthy })[0]).toBe('gate');
  });

  it('skips unhealthy providers', () => {
    const health = { ...healthy, binance: { ok: false, checkedAt: 1 } };
    expect(selectProviders({ capability: 'market_snapshot', health })).not.toContain('binance');
  });

  it('never routes high-risk capability ids', () => {
    expect(selectProviders({ capability: 'place_order', health: healthy })).toEqual([]);
  });
});

describe('resolveExecutionVenue', () => {
  it('defaults production-style execution quotes to Bybit', () => {
    expect(resolveExecutionVenue({ instrument: 'perpetual', health: healthy })).toEqual({
      venue: 'bybit',
      available: true,
    });
  });

  it('honors explicit Binance execution venue', () => {
    expect(resolveExecutionVenue({ executionVenue: 'binance', instrument: 'perpetual', health: healthy })).toEqual({
      venue: 'binance',
      available: true,
    });
  });

  it('does not silently substitute Binance when Bybit execution is unavailable', () => {
    const health = { ...healthy, bybit: { ok: false, checkedAt: 1 } };
    expect(resolveExecutionVenue({ executionVenue: 'bybit', instrument: 'perpetual', health })).toEqual({
      venue: 'bybit',
      available: false,
      reason: 'execution_venue_unavailable',
    });
  });
});
