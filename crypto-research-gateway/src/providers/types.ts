import type { InstrumentType, MarketObservation } from '../normalization/market-normalizer.js';

export type PublicInstrument = Extract<InstrumentType, 'spot' | 'perpetual'>;
export type ProviderId = 'binance' | 'okx' | 'bybit' | 'gate' | 'kucoin';

export type ProviderProbe = {
  ok: boolean;
  latencyMs: number;
  error?: string;
};

export interface PublicMarketProvider {
  id: ProviderId;
  snapshot(symbol: string, instrument: PublicInstrument): Promise<MarketObservation[]>;
  candles(symbol: string, instrument: PublicInstrument, interval: string, limit: number): Promise<unknown>;
  orderbook(symbol: string, instrument: PublicInstrument, limit: number): Promise<unknown>;
  derivatives?(symbol: string): Promise<unknown>;
  healthProbe(): Promise<ProviderProbe>;
}
