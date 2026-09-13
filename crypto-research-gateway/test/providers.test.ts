import { afterEach, describe, expect, it, vi } from 'vitest';
import { BinanceProvider } from '../src/providers/binance.js';
import { BybitProvider } from '../src/providers/bybit.js';
import { OkxProvider } from '../src/providers/okx.js';
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

  it('emits OKX swap bid and ask from ticker timestamp alongside last and mark', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/v5/market/ticker')) {
        return new Response(JSON.stringify({ data: [{ instId: 'BTC-USDT-SWAP', bidPx: '99990', askPx: '100010', last: '100000', ts: '2100' }] }), { status: 200 });
      }
      if (url.includes('/api/v5/public/mark-price')) {
        return new Response(JSON.stringify({ data: [{ instId: 'BTC-USDT-SWAP', markPx: '100002', ts: '2200' }] }), { status: 200 });
      }
      return new Response('unexpected', { status: 404 });
    });
    const observations = await new OkxProvider().snapshot('BTCUSDT', 'perpetual');
    const bySemantic = Object.fromEntries(observations.map((row) => [row.priceSemantic, row]));
    expect(Object.keys(bySemantic).sort()).toEqual(['ask', 'bid', 'last', 'mark']);
    expect(bySemantic.bid.price).toBe(99990);
    expect(bySemantic.ask.price).toBe(100010);
    expect(bySemantic.bid.sourceTimestampMs).toBe(2100);
    expect(bySemantic.mark.sourceTimestampMs).toBe(2200);
  });
});

describe('dynamic scanner perpetual discovery and executed flow', () => {
  it('discovers only active Binance USDT perpetuals and normalizes aggregate taker flow', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/fapi/v1/exchangeInfo')) {
        return new Response(JSON.stringify({ serverTime: 3000, symbols: [
          { symbol: 'BTCUSDT', contractType: 'PERPETUAL', status: 'TRADING', quoteAsset: 'USDT', marginAsset: 'USDT' },
          { symbol: 'ETHUSDT', contractType: 'CURRENT_QUARTER', status: 'TRADING', quoteAsset: 'USDT', marginAsset: 'USDT' },
          { symbol: 'SOLUSDC', contractType: 'PERPETUAL', status: 'TRADING', quoteAsset: 'USDC', marginAsset: 'USDC' },
        ] }), { status: 200 });
      }
      if (url.endsWith('/fapi/v1/ticker/24hr')) {
        return new Response(JSON.stringify([{ symbol: 'BTCUSDT', lastPrice: '100000', quoteVolume: '250000000', closeTime: 3050 }]), { status: 200 });
      }
      if (url.endsWith('/fapi/v1/ticker/bookTicker')) {
        return new Response(JSON.stringify([{ symbol: 'BTCUSDT', bidPrice: '99990', askPrice: '100010', time: 3060 }]), { status: 200 });
      }
      if (url.includes('/fapi/v1/aggTrades')) {
        return new Response(JSON.stringify([
          { p: '100000', q: '0.5', T: 3100, m: false },
          { p: '99990', q: '0.2', T: 3110, m: true },
        ]), { status: 200 });
      }
      return new Response('unexpected', { status: 404 });
    });
    const provider = new BinanceProvider();
    const markets = await provider.listPerpetualMarkets!();
    expect(markets.map((row) => row.symbol)).toEqual(['BTCUSDT']);
    expect(markets[0]).toMatchObject({ venue: 'binance', active: true, bid: 99990, ask: 100010, quoteVolumeUsd: 250000000 });
    const trades = await provider.recentTrades!('BTCUSDT', 50);
    expect(trades.map((row) => row.side)).toEqual(['BUYER_TAKER', 'SELLER_TAKER']);
    expect(trades[0].notional).toBe(50000);
  });

  it('discovers only active Bybit linear USDT perpetuals and normalizes taker side', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/v5/market/instruments-info')) {
        return new Response(JSON.stringify({ time: 4000, result: { nextPageCursor: '', list: [
          { symbol: 'ETHUSDT', status: 'Trading', contractType: 'LinearPerpetual', quoteCoin: 'USDT', settleCoin: 'USDT' },
          { symbol: 'BTCUSD', status: 'Trading', contractType: 'InversePerpetual', quoteCoin: 'USD', settleCoin: 'BTC' },
          { symbol: 'XRPUSDT', status: 'Settled', contractType: 'LinearPerpetual', quoteCoin: 'USDT', settleCoin: 'USDT' },
        ] } }), { status: 200 });
      }
      if (url.includes('/v5/market/tickers?category=linear') && !url.includes('symbol=')) {
        return new Response(JSON.stringify({ time: 4050, result: { list: [
          { symbol: 'ETHUSDT', bid1Price: '2499', ask1Price: '2501', lastPrice: '2500', turnover24h: '90000000' },
        ] } }), { status: 200 });
      }
      if (url.includes('/v5/market/recent-trade')) {
        return new Response(JSON.stringify({ time: 4100, result: { list: [
          { symbol: 'ETHUSDT', price: '2500', size: '2', side: 'Buy', time: '4090' },
          { symbol: 'ETHUSDT', price: '2499', size: '1', side: 'Sell', time: '4095' },
        ] } }), { status: 200 });
      }
      return new Response('unexpected', { status: 404 });
    });
    const provider = new BybitProvider();
    const markets = await provider.listPerpetualMarkets!();
    expect(markets.map((row) => row.symbol)).toEqual(['ETHUSDT']);
    expect(markets[0]).toMatchObject({ venue: 'bybit', bid: 2499, ask: 2501, quoteVolumeUsd: 90000000 });
    const trades = await provider.recentTrades!('ETHUSDT', 10);
    expect(trades.map((row) => row.side)).toEqual(['BUYER_TAKER', 'SELLER_TAKER']);
  });

  it('discovers only live OKX USDT swaps and normalizes ticker/trade evidence', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/api/v5/public/instruments?instType=SWAP')) {
        return new Response(JSON.stringify({ data: [
          { instId: 'SOL-USDT-SWAP', state: 'live', ctType: 'linear', settleCcy: 'USDT' },
          { instId: 'BTC-USD-SWAP', state: 'live', ctType: 'inverse', settleCcy: 'BTC' },
          { instId: 'DOGE-USDT-SWAP', state: 'suspend', ctType: 'linear', settleCcy: 'USDT' },
        ] }), { status: 200 });
      }
      if (url.includes('/api/v5/market/tickers?instType=SWAP')) {
        return new Response(JSON.stringify({ data: [
          { instId: 'SOL-USDT-SWAP', bidPx: '149.9', askPx: '150.1', last: '150', volCcy24h: '1000000', ts: '5050' },
        ] }), { status: 200 });
      }
      if (url.includes('/api/v5/market/trades')) {
        return new Response(JSON.stringify({ data: [
          { instId: 'SOL-USDT-SWAP', px: '150', sz: '10', side: 'buy', ts: '5090' },
          { instId: 'SOL-USDT-SWAP', px: '149.9', sz: '5', side: 'sell', ts: '5095' },
        ] }), { status: 200 });
      }
      return new Response('unexpected', { status: 404 });
    });
    const provider = new OkxProvider();
    const markets = await provider.listPerpetualMarkets!();
    expect(markets.map((row) => row.symbol)).toEqual(['SOLUSDT']);
    expect(markets[0]).toMatchObject({ venue: 'okx', bid: 149.9, ask: 150.1 });
    expect(markets[0].quoteVolumeUsd).toBe(150000000);
    const trades = await provider.recentTrades!('SOLUSDT', 10);
    expect(trades.map((row) => row.side)).toEqual(['BUYER_TAKER', 'SELLER_TAKER']);
    expect(trades[0].notional).toBe(1500);
  });
});
