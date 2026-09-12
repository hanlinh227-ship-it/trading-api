import type { MarketObservation } from '../normalization/market-normalizer.js';
import { fetchJson } from './http.js';
import { asArray, asRecord, positivePrice, probe } from './helpers.js';
import { canonicalSymbol, normalizeProviderSymbol, quoteCurrency } from './symbols.js';
import type { PublicInstrument, PublicMarketProvider } from './types.js';

const BASE = 'https://api.gateio.ws/api/v4';

function firstRow(raw: unknown): Record<string, unknown> {
  const list = asArray(raw);
  if (list.length === 0) throw new Error('provider_empty_data');
  return asRecord(list[0]);
}

export class GateProvider implements PublicMarketProvider {
  readonly id = 'gate' as const;

  async snapshot(symbol: string, instrument: PublicInstrument): Promise<MarketObservation[]> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const received = Date.now();
    const row = instrument === 'spot'
      ? firstRow(await fetchJson(`${BASE}/spot/tickers?currency_pair=${encodeURIComponent(providerSymbol)}`))
      : firstRow(await fetchJson(`${BASE}/futures/usdt/tickers?contract=${encodeURIComponent(providerSymbol)}`));
    const common = {
      provider: this.id,
      venue: this.id,
      symbol: canonicalSymbol(symbol),
      instrumentType: instrument,
      quoteCurrency: quoteCurrency(symbol),
      sourceTimestampMs: received,
      receivedTimestampMs: received,
    };
    const observations: MarketObservation[] = [
      { ...common, priceSemantic: 'last', price: positivePrice(row.last, 'last') },
    ];
    if (instrument === 'perpetual') {
      if (row.mark_price != null) observations.push({ ...common, priceSemantic: 'mark', price: positivePrice(row.mark_price, 'mark_price') });
      if (row.index_price != null) observations.push({ ...common, priceSemantic: 'index', price: positivePrice(row.index_price, 'index_price') });
    }
    return observations;
  }

  async candles(symbol: string, instrument: PublicInstrument, interval: string, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    if (instrument === 'spot') {
      return fetchJson(`${BASE}/spot/candlesticks?currency_pair=${encodeURIComponent(providerSymbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(Math.max(limit, 1), 1000)}`);
    }
    return fetchJson(`${BASE}/futures/usdt/candlesticks?contract=${encodeURIComponent(providerSymbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(Math.max(limit, 1), 2000)}`);
  }

  async orderbook(symbol: string, instrument: PublicInstrument, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    if (instrument === 'spot') {
      return fetchJson(`${BASE}/spot/order_book?currency_pair=${encodeURIComponent(providerSymbol)}&limit=${Math.min(Math.max(limit, 1), 100)}`);
    }
    return fetchJson(`${BASE}/futures/usdt/order_book?contract=${encodeURIComponent(providerSymbol)}&limit=${Math.min(Math.max(limit, 1), 100)}`);
  }

  async derivatives(symbol: string): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, 'perpetual');
    return {
      provider: this.id,
      symbol: providerSymbol,
      ticker: await fetchJson(`${BASE}/futures/usdt/tickers?contract=${encodeURIComponent(providerSymbol)}`),
    };
  }

  async healthProbe() {
    return probe(() => this.snapshot('BTCUSDT', 'spot'));
  }
}
