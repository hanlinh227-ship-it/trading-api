import type { MarketDomain } from './multi-market.js';

const PRIORITY_ORDER: readonly MarketDomain[] = ['crypto', 'forex', 'futures'];

function normalizeIntent(intent: string): string {
  return intent
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function hasToken(tokens: Set<string>, ...choices: string[]): boolean {
  return choices.some((choice) => tokens.has(choice));
}

export function resolveDomainsFromIntent(intent?: string | null): MarketDomain[] {
  if (!intent || intent.trim().length === 0) return [];

  const normalized = normalizeIntent(intent);
  const tokens = new Set(normalized.split(/\s+/).filter(Boolean));
  const matched = new Set<MarketDomain>();

  if (hasToken(tokens, 'coin', 'crypto', 'cryptocurrency')) matched.add('crypto');
  if (hasToken(tokens, 'forex', 'fx')) matched.add('forex');
  if (hasToken(tokens, 'future', 'futures')) matched.add('futures');

  return PRIORITY_ORDER.filter((domain) => matched.has(domain));
}
