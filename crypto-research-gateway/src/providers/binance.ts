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
    if (instrument === 'spot') {
      const row = asRecord(await fetchJson(`${SPOT}/api/v3/ticker/24hr?symbol=${encodeURIComponent(providerSymbol)}`));
      const received = Date.now();
      return [{
        provider: this.id,
        venue: this.id,
        symbol: canonicalSymbol(symbol),
        instrumentType: 'spot',
        quoteCurrency: quoteCurrency(symbol),
        priceSemantic: 'last',
        price: positivePrice(row.lastPrice, 'lastPrice'),
        sourceTimestampMs: numberValue(row.closeTime, 'closeTime'),
        receivedTimestampMs: received,
      }];
    }

    const [bookRaw, lastRaw, premiumRaw] = await Promise.all([
      fetchJson(`${FUTURES}/fapi/v1/ticker/bookTicker?symbol=${encodeURIComponent(providerSymbol)}`),
      fetchJson(`${FUTURES}/fapi/v1/ticker/price?symbol=${encodeURIComponent(providerSymbol)}`),
      fetchJson(`${FUTURES}/fapi/v1/premiumIndex?symbol=${encodeURIComponent(providerSymbol)}`),
    ]);
    const received = Date.now();
    const book = asRecord(bookRaw);
    const last = asRecord(lastRaw);
    const premium = asRecord(premiumRaw);
    const common = {
      provider: this.id,
      venue: this.id,
      symbol: canonicalSymbol(symbol),
      instrumentType: 'perpetual' as const,
      quoteCurrency: quoteCurrency(symbol),
      receivedTimestampMs: received,
    };
    const bookTimestamp = numberValue(book.time, 'time');
    const lastTimestamp = numberValue(last.time, 'time');
    const premiumTimestamp = numberValue(premium.time, 'time');
    return [
      { ...common, priceSemantic: 'bid', price: positivePrice(book.bidPrice, 'bidPrice'), sourceTimestampMs: bookTimestamp },
      { ...common, priceSemantic: 'ask', price: positivePrice(book.askPrice, 'askPrice'), sourceTimestampMs: bookTimestamp },
      { ...common, priceSemantic: 'last', price: positivePrice(last.price, 'price'), sourceTimestampMs: lastTimestamp },
      { ...common, priceSemantic: 'mark', price: positivePrice(premium.markPrice, 'markPrice'), sourceTimestampMs: premiumTimestamp },
      { ...common, priceSemantic: 'index', price: positivePrice(premium.indexPrice, 'indexPrice'), sourceTimestampMs: premiumTimestamp },
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
