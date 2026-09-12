import type { MarketObservation } from '../normalization/market-normalizer.js';
import { fetchJson } from './http.js';
import { asRecord, numberValue, positivePrice, probe, text } from './helpers.js';
import { canonicalSymbol, normalizeProviderSymbol, quoteCurrency } from './symbols.js';
import type { PublicInstrument, PublicMarketProvider } from './types.js';

const SPOT = 'https://data-api.binance.vision';
const FUTURES = 'https://fapi.binance.com';

export class BinanceProvider implements PublicMarketProvider {
  readonly id = 'binance' as const;

  async snapshot(symbol: string, instrument: PublicInstrument): Promise<MarketObservation[]> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const received = Date.now();
    if (instrument === 'spot') {
      const row = asRecord(await fetchJson(`${SPOT}/api/v3/ticker/24hr?symbol=${encodeURIComponent(providerSymbol)}`));
      return [{
        provider: this.id,
        venue: this.id,
        symbol: canonicalSymbol(symbol),
        instrumentType: 'spot',
        quoteCurrency: quoteCurrency(symbol),
        priceSemantic: 'last',
        price: positivePrice(row.lastPrice, 'lastPrice'),
        sourceTimestampMs: numberValue(row.closeTime ?? received, 'closeTime'),
        receivedTimestampMs: received,
      }];
    }

    const [lastRaw, premiumRaw] = await Promise.all([
      fetchJson(`${FUTURES}/fapi/v1/ticker/price?symbol=${encodeURIComponent(providerSymbol)}`),
      fetchJson(`${FUTURES}/fapi/v1/premiumIndex?symbol=${encodeURIComponent(providerSymbol)}`),
    ]);
    const last = asRecord(lastRaw);
    const premium = asRecord(premiumRaw);
    const ts = numberValue(premium.time ?? last.time ?? received, 'time');
    const common = {
      provider: this.id,
      venue: this.id,
      symbol: canonicalSymbol(symbol),
      instrumentType: 'perpetual' as const,
      quoteCurrency: quoteCurrency(symbol),
      sourceTimestampMs: ts,
      receivedTimestampMs: received,
    };
    return [
      { ...common, priceSemantic: 'last', price: positivePrice(last.price, 'price') },
      { ...common, priceSemantic: 'mark', price: positivePrice(premium.markPrice, 'markPrice') },
      { ...common, priceSemantic: 'index', price: positivePrice(premium.indexPrice, 'indexPrice') },
    ];
  }

  async candles(symbol: string, instrument: PublicInstrument, interval: string, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const path = instrument === 'spot' ? '/api/v3/klines' : '/fapi/v1/klines';
    const base = instrument === 'spot' ? SPOT : FUTURES;
    return fetchJson(`${base}${path}?symbol=${encodeURIComponent(providerSymbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(Math.max(limit, 1), 500)}`);
  }

  async orderbook(symbol: string, instrument: PublicInstrument, limit: number): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, instrument);
    const path = instrument === 'spot' ? '/api/v3/depth' : '/fapi/v1/depth';
    const base = instrument === 'spot' ? SPOT : FUTURES;
    return fetchJson(`${base}${path}?symbol=${encodeURIComponent(providerSymbol)}&limit=${Math.min(Math.max(limit, 5), 500)}`);
  }

  async derivatives(symbol: string): Promise<unknown> {
    const providerSymbol = normalizeProviderSymbol(this.id, symbol, 'perpetual');
    const [premium, openInterest] = await Promise.all([
      fetchJson(`${FUTURES}/fapi/v1/premiumIndex?symbol=${encodeURIComponent(providerSymbol)}`),
      fetchJson(`${FUTURES}/fapi/v1/openInterest?symbol=${encodeURIComponent(providerSymbol)}`),
    ]);
    return { provider: this.id, symbol: text(providerSymbol, 'symbol'), premium, openInterest };
  }

  async healthProbe() {
    return probe(() => this.snapshot('BTCUSDT', 'spot'));
  }
}
