import { ALL_MARKET_DOMAINS, resolveMarketScope, type MarketDomain } from './multi-market.js';

export type MarketInstrumentType = 'spot' | 'perpetual' | 'forex' | 'future' | 'index';

export type VerifiedProviderMapping = {
  symbol: string;
  verified: boolean;
};

export type MarketUniverseEntry = {
  domain: MarketDomain;
  canonicalSymbol: string;
  productCode?: string;
  instrumentType: MarketInstrumentType;
  mappings: Record<string, VerifiedProviderMapping>;
};

function entry(
  domain: MarketDomain,
  canonicalSymbol: string,
  instrumentType: MarketInstrumentType,
  mappings: Record<string, VerifiedProviderMapping>,
  productCode?: string,
): MarketUniverseEntry {
  return { domain, canonicalSymbol, instrumentType, mappings, ...(productCode ? { productCode } : {}) };
}

export const DEFAULT_MARKET_UNIVERSE: readonly MarketUniverseEntry[] = [
  entry('crypto', 'BTCUSDT', 'perpetual', { gateway: { symbol: 'BTCUSDT', verified: true } }),
  entry('crypto', 'ETHUSDT', 'perpetual', { gateway: { symbol: 'ETHUSDT', verified: true } }),
  entry('crypto', 'SOLUSDT', 'perpetual', { gateway: { symbol: 'SOLUSDT', verified: true } }),
  entry('crypto', 'XRPUSDT', 'perpetual', { gateway: { symbol: 'XRPUSDT', verified: true } }),

  entry('forex', 'EURUSD', 'forex', { massive: { symbol: 'C:EURUSD', verified: true } }),
  entry('forex', 'GBPUSD', 'forex', { massive: { symbol: 'C:GBPUSD', verified: true } }),
  entry('forex', 'USDJPY', 'forex', { massive: { symbol: 'C:USDJPY', verified: true } }),
  entry('forex', 'USDCHF', 'forex', { massive: { symbol: 'C:USDCHF', verified: true } }),
  entry('forex', 'USDCAD', 'forex', { massive: { symbol: 'C:USDCAD', verified: true } }),
  entry('forex', 'AUDUSD', 'forex', { massive: { symbol: 'C:AUDUSD', verified: true } }),
  entry('forex', 'NZDUSD', 'forex', { massive: { symbol: 'C:NZDUSD', verified: true } }),
  entry('forex', 'EURJPY', 'forex', { massive: { symbol: 'C:EURJPY', verified: true } }),
  entry('forex', 'GBPJPY', 'forex', { massive: { symbol: 'C:GBPJPY', verified: true } }),

  entry('futures', 'ES', 'future', { massive: { symbol: 'ES', verified: true } }, 'ES'),
  entry('futures', 'NQ', 'future', { massive: { symbol: 'NQ', verified: true } }, 'NQ'),
  entry('futures', 'YM', 'future', { massive: { symbol: 'YM', verified: true } }, 'YM'),
  entry('futures', 'RTY', 'future', { massive: { symbol: 'RTY', verified: true } }, 'RTY'),

  entry('indices', 'SPX', 'index', { massive: { symbol: 'I:SPX', verified: true } }),
  entry('indices', 'NDX', 'index', { massive: { symbol: 'I:NDX', verified: true } }),
  entry('indices', 'VIX', 'index', { massive: { symbol: 'I:VIX', verified: true } }),

  entry('metals', 'GC', 'future', { massive: { symbol: 'GC', verified: true } }, 'GC'),
  entry('metals', 'SI', 'future', { massive: { symbol: 'SI', verified: true } }, 'SI'),
  entry('metals', 'HG', 'future', { massive: { symbol: 'HG', verified: true } }, 'HG'),

  entry('commodities', 'CL', 'future', { massive: { symbol: 'CL', verified: true } }, 'CL'),
  entry('commodities', 'NG', 'future', { massive: { symbol: 'NG', verified: true } }, 'NG'),
] as const;

export type UnresolvedUniverseSymbol = {
  domain: MarketDomain;
  symbol: string;
  reason: 'UNVERIFIED_SYMBOL';
};

export type UniverseResolution = {
  entries: MarketUniverseEntry[];
  unresolved: UnresolvedUniverseSymbol[];
};

export function resolveUniverse(
  requestedDomains?: MarketDomain[],
  requestedSymbols?: Partial<Record<MarketDomain, string[]>>,
): UniverseResolution {
  const domains = resolveMarketScope(requestedDomains);
  const entries: MarketUniverseEntry[] = [];
  const unresolved: UnresolvedUniverseSymbol[] = [];

  for (const domain of domains) {
    const domainEntries = DEFAULT_MARKET_UNIVERSE.filter((item) => item.domain === domain);
    const requested = requestedSymbols?.[domain];
    if (!requested || requested.length === 0) {
      entries.push(...domainEntries);
      continue;
    }

    const bySymbol = new Map(domainEntries.map((item) => [item.canonicalSymbol, item]));
    const seen = new Set<string>();
    for (const rawSymbol of requested) {
      const symbol = rawSymbol.trim().toUpperCase();
      if (!symbol || seen.has(symbol)) continue;
      seen.add(symbol);
      const resolved = bySymbol.get(symbol);
      if (resolved) {
        entries.push(resolved);
      } else {
        unresolved.push({ domain, symbol, reason: 'UNVERIFIED_SYMBOL' });
      }
    }
  }

  return { entries, unresolved };
}

export function marketUniverseDomains(): MarketDomain[] {
  const covered = new Set(DEFAULT_MARKET_UNIVERSE.map((item) => item.domain));
  return ALL_MARKET_DOMAINS.filter((domain) => covered.has(domain));
}
