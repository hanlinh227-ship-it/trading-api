import { describe, expect, it } from 'vitest';
import { buildExecutionQuote } from '../src/execution/execution-quote.js';
import type { MarketObservation } from '../src/normalization/market-normalizer.js';

function obs(overrides: Partial<MarketObservation> = {}): MarketObservation {
  return {
    provider: 'bybit',
    venue: 'bybit',
    symbol: 'BTCUSDT',
    instrumentType: 'perpetual',
    quoteCurrency: 'USDT',
    priceSemantic: 'bid',
    price: 100,
    sourceTimestampMs: 9_500,
    receivedTimestampMs: 10_000,
    ...overrides,
  };
}

function healthyBook(): MarketObservation[] {
  return [
    obs({ priceSemantic: 'bid', price: 100 }),
    obs({ priceSemantic: 'ask', price: 100.1 }),
    obs({ priceSemantic: 'last', price: 100.05 }),
    obs({ priceSemantic: 'mark', price: 100.04 }),
    obs({ priceSemantic: 'index', price: 100.03 }),
  ];
}

describe('buildExecutionQuote', () => {
  it('uses ask for LONG and never substitutes last, mark, index or mid', () => {
    const result = buildExecutionQuote({
      venue: 'bybit',
      symbol: 'BTCUSDT',
      instrumentType: 'perpetual',
      side: 'LONG',
      observations: healthyBook(),
    });

    expect(result.status).toBe('OK');
    expect(result.executionVerified).toBe(true);
    expect(result.executableSemantic).toBe('ask');
    expect(result.executablePrice).toBe(100.1);
    expect(result.executablePrice).not.toBe(100.05);
    expect(result.quoteAgeMs).toBe(500);
  });

  it('uses bid for SHORT and never substitutes last, mark, index or mid', () => {
    const result = buildExecutionQuote({
      venue: 'bybit',
      symbol: 'BTCUSDT',
      instrumentType: 'perpetual',
      side: 'SHORT',
      observations: healthyBook(),
    });

    expect(result.status).toBe('OK');
    expect(result.executionVerified).toBe(true);
    expect(result.executableSemantic).toBe('bid');
    expect(result.executablePrice).toBe(100);
  });

  it('fails closed when the executable quote is older than the hard stale threshold', () => {
    const stale = healthyBook().map((row) => ({ ...row, sourceTimestampMs: 4_000, receivedTimestampMs: 10_000 }));
    const result = buildExecutionQuote({
      venue: 'bybit', symbol: 'BTCUSDT', instrumentType: 'perpetual', side: 'LONG', observations: stale,
    });
    expect(result.status).toBe('STALE_PRICE');
    expect(result.executionVerified).toBe(false);
  });

  it('fails closed when a required source timestamp is invalid', () => {
    const invalid = healthyBook().map((row) => ({ ...row, sourceTimestampMs: 0 }));
    const result = buildExecutionQuote({
      venue: 'bybit', symbol: 'BTCUSDT', instrumentType: 'perpetual', side: 'SHORT', observations: invalid,
    });
    expect(result.status).toBe('SEMANTIC_MISMATCH');
    expect(result.executionVerified).toBe(false);
  });

  it('rejects a crossed execution book', () => {
    const crossed = [
      obs({ priceSemantic: 'bid', price: 100.2 }),
      obs({ priceSemantic: 'ask', price: 100.1 }),
    ];
    const result = buildExecutionQuote({
      venue: 'bybit', symbol: 'BTCUSDT', instrumentType: 'perpetual', side: 'LONG', observations: crossed,
    });
    expect(result.status).toBe('SEMANTIC_MISMATCH');
    expect(result.executionVerified).toBe(false);
  });

  it('cross-checks only the same executable semantic across venues', () => {
    const result = buildExecutionQuote({
      venue: 'bybit',
      symbol: 'BTCUSDT',
      instrumentType: 'perpetual',
      side: 'LONG',
      observations: healthyBook(),
      crossVenueObservations: [
        obs({ provider: 'binance', venue: 'binance', priceSemantic: 'ask', price: 100.2 }),
        obs({ provider: 'binance', venue: 'binance', priceSemantic: 'mark', price: 120 }),
        obs({ provider: 'binance', venue: 'binance', priceSemantic: 'bid', price: 80 }),
      ],
    });

    expect(result.status).toBe('OK');
    expect(result.crossVenue).toHaveLength(1);
    expect(result.crossVenue?.[0].semantic).toBe('ask');
  });

  it('returns PRICE_DIVERGENCE for material same-semantic cross-venue disagreement', () => {
    const result = buildExecutionQuote({
      venue: 'bybit',
      symbol: 'BTCUSDT',
      instrumentType: 'perpetual',
      side: 'LONG',
      observations: healthyBook(),
      crossVenueObservations: [
        obs({ provider: 'binance', venue: 'binance', priceSemantic: 'ask', price: 101 }),
      ],
    });

    expect(result.status).toBe('PRICE_DIVERGENCE');
    expect(result.executionVerified).toBe(false);
  });

  it('does not verify a perpetual quote using spot observations', () => {
    const spot = healthyBook().map((row) => ({ ...row, instrumentType: 'spot' as const }));
    const result = buildExecutionQuote({
      venue: 'bybit', symbol: 'BTCUSDT', instrumentType: 'perpetual', side: 'LONG', observations: spot,
    });
    expect(result.status).toBe('SEMANTIC_MISMATCH');
    expect(result.executionVerified).toBe(false);
  });
});
