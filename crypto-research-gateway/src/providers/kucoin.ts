import type { MarketObservation } from '../normalization/market-normalizer.js';
import { fetchJson } from './http.js';
import { asArray, asRecord, numberValue, positivePrice, probe } from './helpers.js';
import { canonicalSymbol, normalizeProviderSymbol, quoteCurrency } from './symbols.js';
import type { PublicInstrument, PublicMarketProvider } from './types.js';

const SPOT_BASE = 'https://api.kucoin.com';
const FUTURES_BASE = 'https://api-futures.kucoin.com';

function unwrapUtaTicker(raw: unknown): { row: Record<string, unknown>; tsMs: number } {
  const root = asRecord(raw);
  const data = asRecord(root.data);
  const list = asArray(data.list);
  if (list.length === 0) throw new Error('provider_empty_data');
  const tsRaw = numberValue(data.ts ?? Date.now() * 1_000_000, 'ts');
  const tsMs = tsRaw > 10_000_000_000_000 ? Math.floor(tsRaw / 1_000_000) : tsRaw;
  return { row: asRecord(list[0]), tsMs };
}

export class KucoinProvider implements PublicMarketProvider {
  readonly id = 'kucoin' as const;

  async snapshot(symbol: string, instrument: PublicInstrument): Promise<MarketObservation[]> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const received = Date.now();
    if (instrument === 'spot') {
      try {
        const { row, tsMs } = unwrapUtaTicker(await fetchJson(`${SPOT_BASE}/api/ua/v1/market/ticker?tradeType=SPOT&symbol=${encodeURIComponent(providerSymbol)}`));
        return [{
          provider: this.id,
          venue: this.id,
          symbol: canonicalSymbol(symbol),
          instrumentType: 'spot',
          quoteCurrency: quoteCurrency(symbol),
          priceSemantic: 'last',
          price: positivePrice(row.lastPrice ?? row.price ?? row.last, 'lastPrice'),
          sourceTimestampMs: tsMs,
          receivedTimestampMs: received,
        }];
      } catch {
        const root = asRecord(await fetchJson(`${SPOT_BASE}/api/v1/market/orderbook/level1?symbol=${encodeURIComponent(providerSymbol)}`));
        const row = asRecord(root.data);
        return [{
          provider: this.id,
          venue: this.id,
          symbol: canonicalSymbol(symbol),
          instrumentType: 'spot',
          quoteCurrency: quoteCurrency(symbol),
          priceSemantic: 'last',
          price: positivePrice(row.price, 'price'),
          sourceTimestampMs: numberValue(row.time ?? received, 'time'),
          receivedTimestampMs: received,
        }];
      }
    }

    const root = asRecord(await fetchJson(`${FUTURES_BASE}/api/v1/ticker?symbol=${encodeURIComponent(providerSymbol)}`));
    const row = asRecord(root.data);
    const common = {
      provider: this.id,
      venue: this.id,
      symbol: canonicalSymbol(symbol),
      instrumentType: 'perpetual' as const,
      quoteCurrency: quoteCurrency(symbol),
      sourceTimestampMs: numberValue(row.ts ?? received, 'ts'),
      receivedTimestampMs: received,
    };
    const observations: MarketObservation[] = [
      { ...common, priceSemantic: 'last', price: positivePrice(row.price, 'price') },
    ];
    if (row.markPrice != null) observations.push({ ...common, priceSemantic: 'mark', price: positivePrice(row.markPrice, 'markPrice') });
    if (row.indexPrice != null) observations.push({ ...common, priceSemantic: 'index', price: positivePrice(row.indexPrice, 'indexPrice') });
    return observations;
  }

  async candles(symbol: string, instrument: PublicInstrument, interval: string, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    if (instrument === 'spot') {
      return fetchJson(`${SPOT_BASE}/api/ua/v2/market/kline?tradeType=SPOT&symbol=${encodeURIComponent(providerSymbol)}&klineType=TRADE&interval=${encodeURIComponent(interval)}&limit=${Math.min(Math.max(limit, 1), 500)}`);
    }
    return fetchJson(`${FUTURES_BASE}/api/v1/kline/query?symbol=${encodeURIComponent(providerSymbol)}&granularity=${encodeURIComponent(interval)}&from=${Math.floor(Date.now() / 1000) - 86_400}`);
  }

  async orderbook(symbol: string, instrument: PublicInstrument, _limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    if (instrument === 'spot') {
      return fetchJson(`${SPOT_BASE}/api/v1/market/orderbook/level2_20?symbol=${encodeURIComponent(providerSymbol)}`);
    }
    return fetchJson(`${FUTURES_BASE}/api/v1/level2/depth20?symbol=${encodeURIComponent(providerSymbol)}`);
  }

  async derivatives(symbol: string): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, 'perpetual');
    return {
      provider: this.id,
      symbol: providerSymbol,
      ticker: await fetchJson(`${FUTURES_BASE}/api/v1/ticker?symbol=${encodeURIComponent(providerSymbol)}`),
    };
  }

  async healthProbe() {
    return probe(() => this.snapshot('BTCUSDT', 'spot'));
  }
}
