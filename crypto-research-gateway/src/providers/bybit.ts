import type { MarketObservation } from '../normalization/market-normalizer.js';
import { fetchJson } from './http.js';
import { asArray, asRecord, numberValue, positivePrice, probe } from './helpers.js';
import { canonicalSymbol, normalizeProviderSymbol, quoteCurrency } from './symbols.js';
import type { PublicInstrument, PublicMarketProvider } from './types.js';

const BASE = 'https://api.bybit.com';

function resultList(raw: unknown): { root: Record<string, unknown>; row: Record<string, unknown> } {
  const root = asRecord(raw);
  const result = asRecord(root.result);
  const list = asArray(result.list);
  if (list.length === 0) throw new Error('provider_empty_data');
  return { root, row: asRecord(list[0]) };
}

export class BybitProvider implements PublicMarketProvider {
  readonly id = 'bybit' as const;

  async snapshot(symbol: string, instrument: PublicInstrument): Promise<MarketObservation[]> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const category = instrument === 'spot' ? 'spot' : 'linear';
    const { root, row } = resultList(await fetchJson(`${BASE}/v5/market/tickers?category=${category}&symbol=${encodeURIComponent(providerSymbol)}`));
    const received = Date.now();
    const ts = numberValue(root.time, 'time');
    const common = {
      provider: this.id,
      venue: this.id,
      symbol: canonicalSymbol(symbol),
      instrumentType: instrument,
      quoteCurrency: quoteCurrency(symbol),
      sourceTimestampMs: ts,
      receivedTimestampMs: received,
    };
    const observations: MarketObservation[] = [
      { ...common, priceSemantic: 'bid', price: positivePrice(row.bid1Price, 'bid1Price') },
      { ...common, priceSemantic: 'ask', price: positivePrice(row.ask1Price, 'ask1Price') },
      { ...common, priceSemantic: 'last', price: positivePrice(row.lastPrice, 'lastPrice') },
    ];
    if (instrument === 'perpetual') {
      if (row.markPrice != null) observations.push({ ...common, priceSemantic: 'mark', price: positivePrice(row.markPrice, 'markPrice') });
      if (row.indexPrice != null) observations.push({ ...common, priceSemantic: 'index', price: positivePrice(row.indexPrice, 'indexPrice') });
    }
    return observations;
  }

  async candles(symbol: string, instrument: PublicInstrument, interval: string, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const category = instrument === 'spot' ? 'spot' : 'linear';
    return fetchJson(`${BASE}/v5/market/kline?category=${category}&symbol=${encodeURIComponent(providerSymbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(Math.max(limit, 1), 1000)}`);
  }

  async orderbook(symbol: string, instrument: PublicInstrument, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const category = instrument === 'spot' ? 'spot' : 'linear';
    return fetchJson(`${BASE}/v5/market/orderbook?category=${category}&symbol=${encodeURIComponent(providerSymbol)}&limit=${Math.min(Math.max(limit, 1), 200)}`);
  }

  async derivatives(symbol: string): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, 'perpetual');
    const [ticker, openInterest] = await Promise.all([
      fetchJson(`${BASE}/v5/market/tickers?category=linear&symbol=${encodeURIComponent(providerSymbol)}`),
      fetchJson(`${BASE}/v5/market/open-interest?category=linear&symbol=${encodeURIComponent(providerSymbol)}&intervalTime=5min&limit=1`),
    ]);
    return { provider: this.id, symbol: providerSymbol, ticker, openInterest };
  }

  async healthProbe() {
    const result = await probe(() => this.snapshot('BTCUSDT', 'spot'));
    if (!result.ok && result.error === 'provider_http_403') {
      return { ...result, error: 'region_restricted_bybit_cloud_region' };
    }
    return result;
  }
}
