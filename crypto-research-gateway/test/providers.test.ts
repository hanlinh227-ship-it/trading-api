import { afterEach, describe, expect, it, vi } from 'vitest';
import { BinanceProvider } from '../src/providers/binance.js';
import { BybitProvider } from '../src/providers/bybit.js';
import { fetchJson } from '../src/providers/http.js';
import { normalizeProviderSymbol } from '../src/providers/index.js';

afterEach(() => vi.restoreAllMocks());

describe('provider safety helpers', () => {
  it('normalizes venue-specific spot symbols', () => {
    expect(normalizeProviderSymbol('binance', 'BTC-USDT', 'spot')).toBe('BTCUSDT');
    expect(normalizeProviderSymbol('okx', 'BTCUSDT', 'spot')).toBe('BTC-USDT');
    expect(normalizeProviderSymbol('gate', 'BTCUSDT', 'spot')).toBe('BTC_USDT');
    expect(normalizeProviderSymbol('kucoin', 'BTCUSDT', 'spot')).toBe('BTC-USDT');
  });

  it('uses GET only and does not add authorization headers', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    await fetchJson('https://example.test/public');
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe('GET');
    expect(new Headers(init?.headers).has('authorization')).toBe(false);
  });

  it('throws on non-2xx provider responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('down', { status: 503 }));
    await expect(fetchJson('https://example.test/public')).rejects.toThrow(/503/);
  });

  it('classifies a Bybit 403 health probe as region-restricted instead of generic failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('forbidden', { status: 403 }));
    const result = await new BybitProvider().healthProbe();
    expect(result.ok).toBe(false);
    expect(result.error).toBe('region_restricted_bybit_cloud_region');
  });
});

describe('venue-native executable quote semantics', () => {
  it('emits Bybit linear bid, ask, last, mark and index from the same ticker timestamp', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        retCode: 0,
        time: 100_000,
        result: {
          list: [{
            symbol: 'BTCUSDT',
            bid1Price: '99990',
            ask1Price: '100010',
            lastPrice: '100000',
            markPrice: '100002',
            indexPrice: '100001',
          }],
        },
      }), { status: 200 }),
    );

    const observations = await new BybitProvider().snapshot('BTCUSDT', 'perpetual');
    const bySemantic = Object.fromEntries(observations.map((row) => [row.priceSemantic, row]));

    expect(Object.keys(bySemantic).sort()).toEqual(['ask', 'bid', 'index', 'last', 'mark']);
    expect(bySemantic.bid.price).toBe(99990);
    expect(bySemantic.ask.price).toBe(100010);
    expect(bySemantic.last.price).toBe(100000);
    expect(bySemantic.mark.price).toBe(100002);
    expect(bySemantic.index.price).toBe(100001);
    expect(observations.every((row) => row.sourceTimestampMs === 100_000)).toBe(true);
  });

  it('keeps Binance USD-M book, last and premium timestamps separate', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/fapi/v1/ticker/bookTicker')) {
        return new Response(JSON.stringify({
          symbol: 'BTCUSDT',
          bidPrice: '99990',
          askPrice: '100010',
          time: 1_100,
        }), { status: 200 });
      }
      if (url.includes('/fapi/v1/ticker/price')) {
        return new Response(JSON.stringify({ symbol: 'BTCUSDT', price: '100000', time: 1_200 }), { status: 200 });
      }
      if (url.includes('/fapi/v1/premiumIndex')) {
        return new Response(JSON.stringify({
          symbol: 'BTCUSDT',
          markPrice: '100002',
          indexPrice: '100001',
          time: 1_300,
        }), { status: 200 });
      }
      return new Response('unexpected', { status: 404 });
    });

    const observations = await new BinanceProvider().snapshot('BTCUSDT', 'perpetual');
    const bySemantic = Object.fromEntries(observations.map((row) => [row.priceSemantic, row]));

    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/fapi/v1/ticker/bookTicker'))).toBe(true);
    expect(Object.keys(bySemantic).sort()).toEqual(['ask', 'bid', 'index', 'last', 'mark']);
    expect(bySemantic.bid.sourceTimestampMs).toBe(1_100);
    expect(bySemantic.ask.sourceTimestampMs).toBe(1_100);
    expect(bySemantic.last.sourceTimestampMs).toBe(1_200);
    expect(bySemantic.mark.sourceTimestampMs).toBe(1_300);
    expect(bySemantic.index.sourceTimestampMs).toBe(1_300);
  });
});
