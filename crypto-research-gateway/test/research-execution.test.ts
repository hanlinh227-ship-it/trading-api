import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketObservation } from '../src/normalization/market-normalizer.js';
import { PROVIDERS } from '../src/providers/index.js';
import { ResearchRuntime } from '../src/research.js';

function quoteRows(venue: 'bybit' | 'binance', instrumentType: 'perpetual' | 'spot' = 'perpetual'): MarketObservation[] {
  return [
    { provider: venue, venue, symbol: 'BTCUSDT', instrumentType, quoteCurrency: 'USDT', priceSemantic: 'bid', price: 100, sourceTimestampMs: 9_500, receivedTimestampMs: 10_000 },
    { provider: venue, venue, symbol: 'BTCUSDT', instrumentType, quoteCurrency: 'USDT', priceSemantic: 'ask', price: 100.1, sourceTimestampMs: 9_500, receivedTimestampMs: 10_000 },
    { provider: venue, venue, symbol: 'BTCUSDT', instrumentType, quoteCurrency: 'USDT', priceSemantic: 'last', price: 100.05, sourceTimestampMs: 9_500, receivedTimestampMs: 10_000 },
    { provider: venue, venue, symbol: 'BTCUSDT', instrumentType, quoteCurrency: 'USDT', priceSemantic: 'mark', price: 100.04, sourceTimestampMs: 9_500, receivedTimestampMs: 10_000 },
    { provider: venue, venue, symbol: 'BTCUSDT', instrumentType, quoteCurrency: 'USDT', priceSemantic: 'index', price: 100.03, sourceTimestampMs: 9_500, receivedTimestampMs: 10_000 },
  ];
}

async function runtimeWithHealth(health: Partial<Record<keyof typeof PROVIDERS, boolean>>) {
  for (const [id, provider] of Object.entries(PROVIDERS)) {
    vi.spyOn(provider, 'healthProbe').mockResolvedValue({
      ok: health[id as keyof typeof PROVIDERS] ?? false,
      latencyMs: 1,
    });
  }
  const runtime = new ResearchRuntime();
  await runtime.probeAll();
  return runtime;
}

afterEach(() => vi.restoreAllMocks());

describe('ResearchRuntime execution_quote', () => {
  it('uses Bybit as default execution source and Binance only as same-semantic cross-check', async () => {
    const runtime = await runtimeWithHealth({ bybit: true, binance: true });
    vi.spyOn(PROVIDERS.bybit, 'snapshot').mockResolvedValue(quoteRows('bybit'));
    vi.spyOn(PROVIDERS.binance, 'snapshot').mockResolvedValue(quoteRows('binance'));

    const result = await runtime.runMarket({
      action: 'execution_quote' as never,
      symbol: 'BTCUSDT',
      instrument: 'perpetual',
      side: 'LONG',
    } as never);

    expect(result.ok).toBe(true);
    expect((result.executionQuote as { venue: string }).venue).toBe('bybit');
    expect((result.executionQuote as { executableSemantic: string }).executableSemantic).toBe('ask');
  });

  it('fails closed when requested Bybit is unavailable even if Binance is healthy', async () => {
    const runtime = await runtimeWithHealth({ bybit: false, binance: true });
    const binanceSnapshot = vi.spyOn(PROVIDERS.binance, 'snapshot').mockResolvedValue(quoteRows('binance'));

    const result = await runtime.runMarket({
      action: 'execution_quote' as never,
      symbol: 'BTCUSDT',
      instrument: 'perpetual',
      side: 'SHORT',
      executionVenue: 'bybit',
    } as never);

    expect(result.ok).toBe(false);
    expect(result.error).toBe('VENUE_UNAVAILABLE');
    expect(binanceSnapshot).not.toHaveBeenCalled();
  });

  it('honors explicit Binance execution venue', async () => {
    const runtime = await runtimeWithHealth({ bybit: true, binance: true });
    vi.spyOn(PROVIDERS.bybit, 'snapshot').mockResolvedValue(quoteRows('bybit'));
    vi.spyOn(PROVIDERS.binance, 'snapshot').mockResolvedValue(quoteRows('binance'));

    const result = await runtime.runMarket({
      action: 'execution_quote' as never,
      symbol: 'BTCUSDT',
      instrument: 'perpetual',
      side: 'SHORT',
      executionVenue: 'binance',
    } as never);

    expect(result.ok).toBe(true);
    expect((result.executionQuote as { venue: string }).venue).toBe('binance');
    expect((result.executionQuote as { executableSemantic: string }).executableSemantic).toBe('bid');
  });

  it('classifies Binance USD-M HTTP 451 as a cloud-region restriction', async () => {
    const runtime = await runtimeWithHealth({ bybit: false, binance: true });
    vi.spyOn(PROVIDERS.binance, 'snapshot').mockRejectedValue(new Error('provider_http_451'));

    const result = await runtime.runMarket({
      action: 'execution_quote' as never,
      symbol: 'BTCUSDT',
      instrument: 'perpetual',
      side: 'LONG',
      executionVenue: 'binance',
    } as never);

    expect(result.ok).toBe(false);
    expect(result.error).toBe('VENUE_UNAVAILABLE');
    expect(result.failures).toEqual([
      { provider: 'binance', error: 'region_restricted_binance_futures_cloud_region' },
    ]);
  });

  it('does not compare a secondary Spot quote against a Perpetual execution quote', async () => {
    const runtime = await runtimeWithHealth({ bybit: true, binance: true });
    vi.spyOn(PROVIDERS.bybit, 'snapshot').mockResolvedValue(quoteRows('bybit', 'perpetual'));
    vi.spyOn(PROVIDERS.binance, 'snapshot').mockResolvedValue(quoteRows('binance', 'spot'));

    const result = await runtime.runMarket({
      action: 'execution_quote' as never,
      symbol: 'BTCUSDT',
      instrument: 'perpetual',
      side: 'LONG',
    } as never);

    expect(result.ok).toBe(true);
    expect((result.executionQuote as { status: string }).status).toBe('OK');
    expect((result.executionQuote as { crossVenue?: unknown[] }).crossVenue).toEqual([]);
  });
});
