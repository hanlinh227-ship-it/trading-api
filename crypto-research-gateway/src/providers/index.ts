import { BinanceProvider } from './binance.js';
import { BybitProvider } from './bybit.js';
import { GateProvider } from './gate.js';
import { KucoinProvider } from './kucoin.js';
import { OkxProvider } from './okx.js';
import { normalizeProviderSymbol } from './symbols.js';
import type { ProviderId, PublicMarketProvider } from './types.js';

export { normalizeProviderSymbol } from './symbols.js';
export type { ProviderId, PublicMarketProvider, PublicInstrument } from './types.js';

export const PROVIDERS: Record<ProviderId, PublicMarketProvider> = {
  binance: new BinanceProvider(),
  okx: new OkxProvider(),
  bybit: new BybitProvider(),
  gate: new GateProvider(),
  kucoin: new KucoinProvider(),
};

export function getProvider(id: string): PublicMarketProvider | undefined {
  return PROVIDERS[id as ProviderId];
}

export const providerSymbol = normalizeProviderSymbol;
