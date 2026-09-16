import { ALL_MARKET_DOMAINS, type MarketDomain } from './multi-market.js';

const FOREX_PAIRS = [
  'eurusd', 'gbpusd', 'usdjpy', 'usdchf', 'usdcad', 'audusd', 'nzdusd', 'eurjpy', 'gbpjpy',
];

const DOMAIN_PATTERNS: Record<MarketDomain, RegExp[]> = {
  crypto: [
    /\bcrypto\b/i,
    /\bcoin(?:s)?\b/i,
    /\bbitcoin\b/i,
    /\bbtc\b/i,
    /\bethereum\b/i,
    /\beth\b/i,
    /\baltcoin(?:s)?\b/i,
  ],
  forex: [
    /\bforex\b/i,
    /\bfx\b/i,
    new RegExp(`\\b(?:${FOREX_PAIRS.join('|')})\\b`, 'i'),
  ],
  futures: [
    /\bfutures?\b/i,
    /\bnq\b/i,
    /\bmnq\b/i,
    /\bmes\b/i,
    /\brty\b/i,
    /\bym\b/i,
  ],
  indices: [
    /\bindices\b/i,
    /\bindex\b/i,
    /\bspx\b/i,
    /\bndx\b/i,
    /\bvix\b/i,
  ],
  metals: [
    /\bmetals?\b/i,
    /\bgold\b/i,
    /\bsilver\b/i,
    /\bxau(?:usd)?\b/i,
    /\bxag(?:usd)?\b/i,
  ],
  commodities: [
    /\bcommodit(?:y|ies)\b/i,
    /\bcrude\b/i,
    /\boil\b/i,
    /\bwti\b/i,
    /\bnatural\s+gas\b/i,
  ],
};

export function inferMarketDomainsFromIntent(intent?: string): MarketDomain[] {
  const value = intent?.trim();
  if (!value) return [];

  return ALL_MARKET_DOMAINS.filter((domain) =>
    DOMAIN_PATTERNS[domain].some((pattern) => pattern.test(value)));
}
