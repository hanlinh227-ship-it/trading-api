import type {
  MarketDomain,
  OpportunityCandidate,
  ResearchFreshness,
  VerifiedChartMapping,
} from './multi-market.js';

export type ObservationSourceType = 'connector' | 'gateway';
export type ObservationDelayClass = 'REALTIME' | 'DELAYED' | 'UNKNOWN';
export type ObservationEntitlement = 'VERIFIED_REALTIME' | 'VERIFIED_DELAYED' | 'UNVERIFIED';
export type ObservationInstrumentType = 'spot' | 'perpetual' | 'forex' | 'future' | 'index';
export type ObservationEvidenceKind = 'quote' | 'snapshot' | 'bar' | 'trade' | 'session' | 'context';

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
  latencyMs?: number;
  delayClass?: ObservationDelayClass;
  entitlement?: ObservationEntitlement;
  instrumentType?: ObservationInstrumentType;
  providerSymbol?: string;
  canonicalSymbol?: string;
  contractExpiry?: string;
  evidenceKind?: ObservationEvidenceKind;
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

export type CandidateBuildResult = {
  candidate?: OpportunityCandidate;
  blockedReasons: string[];
};

export type CandidateBatchResult = {
  candidates: OpportunityCandidate[];
  blocked: Array<{ domain: MarketDomain; symbol: string; reasons: string[] }>;
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

function freshestAllowed(observations: readonly NormalizedMarketObservation[]): ResearchFreshness {
  return observations.some((item) => item.freshness === 'DEGRADED') ? 'DEGRADED' : 'FRESH';
}

function selectStructureBars(observations: readonly NormalizedMarketObservation[]): NormalizedMarketObservation[] | null {
  const byTimeframe = new Map<string, NormalizedMarketObservation[]>();
  for (const observation of observations) {
    const current = byTimeframe.get(observation.timeframe) ?? [];
    current.push(observation);
    byTimeframe.set(observation.timeframe, current);
  }

  const preference = ['15m', '1h', '5m'];
  const candidates = [...byTimeframe.entries()]
    .filter(([, items]) => items.length >= 3)
    .sort(([left], [right]) => {
      const leftIndex = preference.indexOf(left);
      const rightIndex = preference.indexOf(right);
      const leftRank = leftIndex === -1 ? preference.length : leftIndex;
      const rightRank = rightIndex === -1 ? preference.length : rightIndex;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return left.localeCompare(right);
    });

  if (candidates.length === 0) return null;
  return candidates[0][1]
    .slice()
    .sort((left, right) => Date.parse(left.eventTime) - Date.parse(right.eventTime));
}

function uniqueProvenance(observations: readonly NormalizedMarketObservation[]): string[] {
  return [...new Set(observations.map((item) => `${item.sourceType}:${item.source}`))];
}

function verifiedChart(observations: readonly NormalizedMarketObservation[]): VerifiedChartMapping | undefined {
  for (let index = observations.length - 1; index >= 0; index -= 1) {
    const chart = observations[index].chart;
    if (chart?.verified === true) return chart;
  }
  return undefined;
}

export function buildCandidateFromObservations(
  domain: MarketDomain,
  symbol: string,
  observations: readonly NormalizedMarketObservation[],
): CandidateBuildResult {
  const relevant = observations.filter((item) => item.domain === domain && item.symbol === symbol);
  if (relevant.length === 0) {
    return { blockedReasons: ['NO_USABLE_EVIDENCE'] };
  }

  if (relevant.some((item) => item.freshness === 'STALE' || item.freshness === 'UNKNOWN')) {
    return { blockedReasons: ['STALE_OR_UNKNOWN_EVIDENCE'] };
  }

  if (relevant.some((item) => validateObservationSemantics(item).length > 0)) {
    return { blockedReasons: ['INVALID_OBSERVATION'] };
  }

  const bars = selectStructureBars(relevant);
  if (!bars) {
    return { blockedReasons: ['INSUFFICIENT_STRUCTURE_EVIDENCE'] };
  }

  const closes = bars.map((item) => item.close);
  const rising = closes.slice(1).every((close, index) => close > closes[index]);
  const falling = closes.slice(1).every((close, index) => close < closes[index]);
  if (rising === falling) {
    return { blockedReasons: ['AMBIGUOUS_STRUCTURE'] };
  }

  const direction = rising ? 'LONG' as const : 'SHORT' as const;
  const minLow = Math.min(...bars.map((item) => item.low));
  const maxHigh = Math.max(...bars.map((item) => item.high));
  const totalRange = Math.max(maxHigh - minLow, Number.EPSILON);
  const directionalMove = Math.abs(bars[bars.length - 1].close - bars[0].close);
  const structureStrength = Math.max(0.55, Math.min(0.95, 0.55 + (directionalMove / totalRange) * 0.4));
  const latest = bars[bars.length - 1];
  const hasSpread = latest.bid !== undefined && latest.ask !== undefined;
  const mid = hasSpread ? ((latest.bid as number) + (latest.ask as number)) / 2 : latest.close;
  const spreadBps = hasSpread && mid > 0
    ? (((latest.ask as number) - (latest.bid as number)) / mid) * 10_000
    : 0;
  const qualityStrength = Math.max(0.45, Math.min(0.9, 0.9 - spreadBps / 100));
  const freshness = freshestAllowed(bars);
  const score = Math.max(0, Math.min(100, Number(((structureStrength * 70) + (qualityStrength * 30)).toFixed(4))));
  const invalidation = direction === 'LONG'
    ? `structure_below_${minLow}`
    : `structure_above_${maxHigh}`;

  const candidate: OpportunityCandidate = {
    id: `${domain}:${symbol}:${direction.toLowerCase()}`,
    domain,
    symbol,
    direction,
    rawScore: score,
    scoreScale: { min: 0, max: 100 },
    confidence: Number(structureStrength.toFixed(4)),
    riskReward: 2,
    invalidation,
    freshness,
    dataConflict: false,
    provenance: uniqueProvenance(bars),
    evidence: [
      {
        id: 'structure',
        direction,
        strength: Number(structureStrength.toFixed(4)),
        freshness,
        source: 'autonomous-structure-builder',
      },
      {
        id: 'price_quality',
        direction,
        strength: Number(qualityStrength.toFixed(4)),
        freshness,
        source: 'autonomous-price-quality',
      },
    ],
    chart: verifiedChart(bars),
  };

  return { candidate, blockedReasons: [] };
}

export function buildCandidatesFromObservations(
  observations: readonly NormalizedMarketObservation[],
): CandidateBatchResult {
  const candidates: OpportunityCandidate[] = [];
  const blocked: CandidateBatchResult['blocked'] = [];

  for (const [key, grouped] of groupObservations(observations)) {
    const [domainToken, ...symbolParts] = key.split(':');
    const domain = domainToken as MarketDomain;
    const symbol = symbolParts.join(':');
    const result = buildCandidateFromObservations(domain, symbol, grouped);
    if (result.candidate) {
      candidates.push(result.candidate);
    } else {
      blocked.push({ domain, symbol, reasons: result.blockedReasons });
    }
  }

  return { candidates, blocked };
}
