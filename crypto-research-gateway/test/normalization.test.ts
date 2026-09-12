import { describe, expect, it } from 'vitest';
import { resolveObservations } from '../src/normalization/conflict-resolver.js';
import type { MarketObservation } from '../src/normalization/market-normalizer.js';

const base: MarketObservation = {
  provider: 'binance',
  venue: 'binance',
  symbol: 'BTCUSDT',
  instrumentType: 'spot',
  quoteCurrency: 'USDT',
  priceSemantic: 'last',
  price: 100000,
  sourceTimestampMs: 1_000,
  receivedTimestampMs: 1_100,
};

describe('resolveObservations', () => {
  it('does not merge spot and perpetual observations', () => {
    const result = resolveObservations([base, { ...base, provider: 'bybit', instrumentType: 'perpetual' }]);
    expect(result.status).toBe('conflict');
  });

  it('does not merge last and mark price semantics', () => {
    const result = resolveObservations([base, { ...base, provider: 'okx', priceSemantic: 'mark' }]);
    expect(result.status).toBe('conflict');
  });

  it('flags materially divergent equivalent prices instead of averaging them', () => {
    const result = resolveObservations([base, { ...base, provider: 'okx', price: 100500 }], 30);
    expect(result.status).toBe('conflict');
    expect(result.observations).toHaveLength(2);
  });

  it('keeps equivalent observations without inventing a consensus price', () => {
    const result = resolveObservations([base, { ...base, provider: 'okx', price: 100020 }], 30);
    expect(result.status).toBe('ok');
    expect(result.observations.map((x) => x.provider)).toEqual(['binance', 'okx']);
  });
});
