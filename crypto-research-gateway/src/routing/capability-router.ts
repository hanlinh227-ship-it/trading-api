export type ProviderHealth = Record<string, {
  ok: boolean;
  checkedAt: number;
  latencyMs?: number;
  error?: string;
}>;

export type ExecutionVenue = 'bybit' | 'binance';

const PROVIDER_ORDER = ['binance', 'okx', 'bybit', 'gate', 'kucoin'] as const;
const SAFE_CAPABILITIES = new Set([
  'market_snapshot',
  'market_candles',
  'market_orderbook',
  'market_execution_quote',
  'derivatives_funding_oi',
  'token_research',
  'token_risk_check',
  'crypto_news_research',
]);

const WRITE_PATTERN = /(place|cancel|amend|close)[_-]?order|withdraw|transfer|swap|bridge|wallet|payment|pay|broadcast|sign|leverage/i;

export function isResearchSafeCapability(capability: string): boolean {
  return SAFE_CAPABILITIES.has(capability) && !WRITE_PATTERN.test(capability);
}

export function selectProviders(input: {
  capability: string;
  preferredVenue?: string;
  maxCandidates?: number;
  health: ProviderHealth;
}): string[] {
  if (!isResearchSafeCapability(input.capability)) return [];

  const max = Math.max(0, Math.min(input.maxCandidates ?? 3, 3));
  const healthy = PROVIDER_ORDER.filter((id) => input.health[id]?.ok === true);
  const preferred = input.preferredVenue?.toLowerCase();
  const ordered = preferred && healthy.includes(preferred as (typeof PROVIDER_ORDER)[number])
    ? [preferred, ...healthy.filter((id) => id !== preferred)]
    : healthy;

  return ordered.slice(0, max);
}

export function resolveExecutionVenue(input: {
  executionVenue?: ExecutionVenue;
  instrument: 'spot' | 'perpetual';
  health: ProviderHealth;
}): { venue: ExecutionVenue; available: boolean; reason?: string } {
  void input.instrument;
  const venue: ExecutionVenue = input.executionVenue ?? 'bybit';
  if (input.health[venue]?.ok === true) {
    return { venue, available: true };
  }
  return {
    venue,
    available: false,
    reason: 'execution_venue_unavailable',
  };
}
