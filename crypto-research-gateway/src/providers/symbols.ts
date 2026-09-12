import type { ProviderId, PublicInstrument } from './types.js';

const QUOTES = ['USDT', 'USDC', 'USD', 'BTC', 'ETH'] as const;

export function splitCanonicalSymbol(input: string): { base: string; quote: string } {
  const compact = input.toUpperCase().replace(/[-_/]/g, '');
  const quote = QUOTES.find((candidate) => compact.endsWith(candidate));
  if (!quote || compact.length <= quote.length) {
    throw new Error('unsupported_symbol_format');
  }
  return { base: compact.slice(0, -quote.length), quote };
}

export function normalizeProviderSymbol(provider: ProviderId, symbol: string, instrument: PublicInstrument): string {
  const { base, quote } = splitCanonicalSymbol(symbol);
  if (provider === 'binance' || provider === 'bybit') return `${base}${quote}`;
  if (provider === 'okx') return instrument === 'perpetual' ? `${base}-${quote}-SWAP` : `${base}-${quote}`;
  if (provider === 'gate') return `${base}_${quote}`;
  const kuBase = base === 'BTC' ? 'XBT' : base;
  return instrument === 'perpetual' ? `${kuBase}${quote}M` : `${base}-${quote}`;
}

export function canonicalSymbol(symbol: string): string {
  const { base, quote } = splitCanonicalSymbol(symbol);
  return `${base}${quote}`;
}

export function quoteCurrency(symbol: string): string {
  return splitCanonicalSymbol(symbol).quote;
}
