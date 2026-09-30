import type { MarketDomain } from './multi-market.js';

const PRIORITY_ORDER: readonly MarketDomain[] = ['crypto', 'forex', 'futures'];

const CRYPTO_SYMBOLS: Readonly<Record<string, string>> = {
  bitcoin: 'BTCUSDT',
  btc: 'BTCUSDT',
  btcusdt: 'BTCUSDT',
  ethereum: 'ETHUSDT',
  eth: 'ETHUSDT',
  ethusdt: 'ETHUSDT',
  solana: 'SOLUSDT',
  sol: 'SOLUSDT',
  solusdt: 'SOLUSDT',
  xrp: 'XRPUSDT',
  xrpusdt: 'XRPUSDT',
};

const FOREX_SYMBOLS = [
  'EURUSD',
  'GBPUSD',
  'USDJPY',
  'USDCHF',
  'USDCAD',
  'AUDUSD',
  'NZDUSD',
  'EURJPY',
  'GBPJPY',
] as const;

const FUTURES_SYMBOLS = ['ES', 'NQ', 'YM', 'RTY'] as const;

export type IntentSymbolSelection = Partial<Record<MarketDomain, string[]>>;

function normalizeIntent(intent: string): string {
  return intent
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function intentTokens(intent?: string | null): Set<string> {
  if (!intent || intent.trim().length === 0) return new Set();
  return new Set(normalizeIntent(intent).split(/\s+/).filter(Boolean));
}

function hasToken(tokens: Set<string>, ...choices: string[]): boolean {
  return choices.some((choice) => tokens.has(choice));
}

function addSymbol(
  selection: IntentSymbolSelection,
  domain: MarketDomain,
  symbol: string,
): void {
  const current = selection[domain] ?? [];
  if (!current.includes(symbol)) selection[domain] = [...current, symbol];
}

export function resolveSymbolsFromIntent(intent?: string | null): IntentSymbolSelection {
  const tokens = intentTokens(intent);
  if (tokens.size === 0) return {};

  const selection: IntentSymbolSelection = {};

  for (const [alias, canonical] of Object.entries(CRYPTO_SYMBOLS)) {
    if (tokens.has(alias)) addSymbol(selection, 'crypto', canonical);
  }
  for (const symbol of FOREX_SYMBOLS) {
    if (tokens.has(symbol.toLowerCase())) addSymbol(selection, 'forex', symbol);
  }
  for (const symbol of FUTURES_SYMBOLS) {
    if (tokens.has(symbol.toLowerCase())) addSymbol(selection, 'futures', symbol);
  }

  return selection;
}

export function resolveDomainsFromIntent(intent?: string | null): MarketDomain[] {
  const tokens = intentTokens(intent);
  if (tokens.size === 0) return [];

  const matched = new Set<MarketDomain>();

  if (hasToken(tokens, 'coin', 'crypto', 'cryptocurrency')) matched.add('crypto');
  if (hasToken(tokens, 'forex', 'fx')) matched.add('forex');
  if (hasToken(tokens, 'future', 'futures')) matched.add('futures');

  const symbolSelection = resolveSymbolsFromIntent(intent);
  for (const domain of PRIORITY_ORDER) {
    if ((symbolSelection[domain]?.length ?? 0) > 0) matched.add(domain);
  }

  return PRIORITY_ORDER.filter((domain) => matched.has(domain));
}
