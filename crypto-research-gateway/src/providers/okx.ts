import type { MarketObservation } from '../normalization/market-normalizer.js';
import { fetchJson } from './http.js';
import { asArray, asRecord, numberValue, positivePrice, probe } from './helpers.js';
import { canonicalSymbol, normalizeProviderSymbol, quoteCurrency } from './symbols.js';
import type { PublicInstrument, PublicMarketProvider } from './types.js';

const BASE = 'https://www.okx.com';

function firstData(raw: unknown): Record<string, unknown> {
  const root = asRecord(raw);
  const data = asArray(root.data);
  if (data.length === 0) throw new Error('provider_empty_data');
  return asRecord(data[0]);
}

export class OkxProvider implements PublicMarketProvider {
  readonly id = 'okx' as const;

  async snapshot(symbol: string, instrument: PublicInstrument): Promise<MarketObservation[]> {
    const instId = normalizeProviderSymbol(this.id, symbol, instrument);
    const received = Date.now();
    const ticker = firstData(await fetchJson(`${BASE}/api/v5/market/ticker?instId=${encodeURIComponent(instId)}`));
    const ts = numberValue(ticker.ts ?? received, 'ts');
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
      { ...common, priceSemantic: 'last', price: positivePrice(ticker.last, 'last') },
    ];
    if (instrument === 'perpetual') {
      const mark = firstData(await fetchJson(`${BASE}/api/v5/public/mark-price?instType=SWAP&instId=${encodeURIComponent(instId)}`));
      observations.push({ ...common, priceSemantic: 'mark', price: positivePrice(mark.markPx, 'markPx'), sourceTimestampMs: numberValue(mark.ts ?? ts, 'ts') });
    }
    return observations;
  }

  async candles(symbol: string, instrument: PublicInstrument, interval: string, limit: number): Promise<unknown> {
    const instId = normalizeProviderSymbol(this.id, symbol, instrument);
    return fetchJson(`${BASE}/api/v5/market/candles?instId=${encodeURIComponent(instId)}&bar=${encodeURIComponent(interval)}&limit=${Math.min(Math.max(limit, 1), 300)}`);
  }

  async orderbook(symbol: string, instrument: PublicInstrument, limit: number): Promise<unknown> {
    const instId = normalizeProviderSymbol(this.id, symbol, instrument);
    return fetchJson(`${BASE}/api/v5/market/books?instId=${encodeURIComponent(instId)}&sz=${Math.min(Math.max(limit, 1), 400)}`);
  }

  async derivatives(symbol: string): Promise<unknown> {
    const instId = normalizeProviderSymbol(this.id, symbol, 'perpetual');
    const [funding, openInterest] = await Promise.all([
      fetchJson(`${BASE}/api/v5/public/funding-rate?instId=${encodeURIComponent(instId)}`),
      fetchJson(`${BASE}/api/v5/public/open-interest?instType=SWAP&instId=${encodeURIComponent(instId)}`),
    ]);
    return { provider: this.id, symbol: instId, funding, openInterest };
  }

  async healthProbe() {
    return probe(() => this.snapshot('BTCUSDT', 'spot'));
  }
}
