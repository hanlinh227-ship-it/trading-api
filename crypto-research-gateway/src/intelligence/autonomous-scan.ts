import type {
  MarketDomain,
  ResearchFreshness,
  VerifiedChartMapping,
} from './multi-market.js';

export type ObservationSourceType = 'connector' | 'gateway';

export type NormalizedMarketObservation = {
  id: string;
  domain: MarketDomain;
  symbol: string;
  source: string;
  sourceType: ObservationSourceType;
  eventTime: string;
  ingestTime: string;
  freshness: ResearchFreshness;
  timeframe: string;
  open: number;
  high: number;
  low: number;
  close: number;
  bid?: number;
  ask?: number;
  volume?: number;
  session?: string;
  metadata?: Record<string, string | number | boolean | null>;
  chart?: VerifiedChartMapping;
};

export type TimeframePlan = {
  context: '1h';
  entry: '15m';
  fast: '5m';
};

export type CoverageRecord = {
  domain: MarketDomain;
  requested: boolean;
  usableObservationCount: number;
  status: 'COVERED' | 'GAP';
  reasons: string[];
};

export type AutonomousResearchRequest = {
  intent?: string;
  requestedDomains?: MarketDomain[];
  symbols?: Partial<Record<MarketDomain, string[]>>;
  externalObservations?: NormalizedMarketObservation[];
  maxResults?: number;
};

export function buildTimeframePlan(): TimeframePlan {
  return { context: '1h', entry: '15m', fast: '5m' };
}

export function validateObservationSemantics(observation: NormalizedMarketObservation): string[] {
  const reasons: string[] = [];
  const prices = [observation.open, observation.high, observation.low, observation.close];
  if (observation.bid !== undefined) prices.push(observation.bid);
  if (observation.ask !== undefined) prices.push(observation.ask);
  if (observation.volume !== undefined) prices.push(observation.volume);

  if (prices.some((value) => !Number.isFinite(value))) {
    reasons.push('NON_FINITE_PRICE');
    return reasons;
  }

  if (
    observation.high < observation.low
    || observation.high < observation.open
    || observation.high < observation.close
    || observation.low > observation.open
    || observation.low > observation.close
  ) {
    reasons.push('INVALID_OHLC');
  }

  if (
    observation.bid !== undefined
    && observation.ask !== undefined
    && observation.ask < observation.bid
  ) {
    reasons.push('INVALID_SPREAD');
  }

  if (
    Number.isNaN(Date.parse(observation.eventTime))
    || Number.isNaN(Date.parse(observation.ingestTime))
  ) {
    reasons.push('INVALID_TIMESTAMP');
  }

  return reasons;
}

export function groupObservations(
  observations: readonly NormalizedMarketObservation[],
): Map<string, NormalizedMarketObservation[]> {
  const grouped = new Map<string, NormalizedMarketObservation[]>();
  for (const observation of observations) {
    const key = `${observation.domain}:${observation.symbol}`;
    const current = grouped.get(key) ?? [];
    current.push(observation);
    grouped.set(key, current);
  }
  return grouped;
}
