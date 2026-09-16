import type { ResearchLevels } from './research-levels.js';

export const ALL_MARKET_DOMAINS = [
  'crypto',
  'forex',
  'futures',
  'indices',
  'metals',
  'commodities',
] as const;

export type MarketDomain = (typeof ALL_MARKET_DOMAINS)[number];
export type TradeDirection = 'LONG' | 'SHORT';
export type EvidenceDirection = TradeDirection | 'NO_TRADE';
export type ResearchFreshness = 'FRESH' | 'DEGRADED' | 'STALE' | 'UNKNOWN';

export type MarketProfile = {
  domain: MarketDomain;
  researchOnly: true;
  productionExecutionAuthority: false;
  requiredEvidence: readonly string[];
};

export type CandidateEvidence = {
  id: string;
  direction: EvidenceDirection;
  strength: number;
  freshness: ResearchFreshness;
  source: string;
};

export type ScoreScale = {
  min: number;
  max: number;
};

export type VerifiedChartMapping = {
  provider: 'tradingview';
  symbol: string;
  timeframe?: string;
  verified: boolean;
};

export type OpportunityCandidate = {
  id: string;
  domain: MarketDomain;
  symbol: string;
  direction: TradeDirection;
  rawScore: number;
  scoreScale: ScoreScale;
  confidence: number;
  riskReward: number;
  invalidation?: string;
  freshness: ResearchFreshness;
  dataConflict?: boolean;
  provenance: string[];
  evidence: CandidateEvidence[];
  chart?: VerifiedChartMapping;
  levels?: ResearchLevels;
};

export type ChallengeResult = {
  status: 'PASS' | 'NO_TRADE';
  reasons: string[];
};

export type TradingViewNavigationHint = {
  mode: 'VERIFIED_SYMBOL' | 'SYMBOL_SEARCH';
  query: string;
};

export type ChartContext = {
  provider: 'tradingview';
  requestedSymbol: string;
  symbol: string | null;
  timeframe: string | null;
  mappingStatus: 'VERIFIED' | 'UNVERIFIED';
  navigationHint: TradingViewNavigationHint;
};

export type RankedOpportunity = OpportunityCandidate & {
  normalizedScore: number;
  chartContext: ChartContext;
};

export type OpportunityRanking = {
  decision: 'TOP_SETUP' | 'NO_TRADE';
  ranked: RankedOpportunity[];
  blocked: Array<{ id: string; reasons: string[] }>;
};

const PROFILES: Record<MarketDomain, MarketProfile> = {
  crypto: {
    domain: 'crypto',
    researchOnly: true,
    productionExecutionAuthority: false,
    requiredEvidence: ['structure', 'price_quality', 'freshness', 'conflict_check'],
  },
  forex: {
    domain: 'forex',
    researchOnly: true,
    productionExecutionAuthority: false,
    requiredEvidence: ['structure', 'session_context', 'freshness'],
  },
  futures: {
    domain: 'futures',
    researchOnly: true,
    productionExecutionAuthority: false,
    requiredEvidence: ['current_contract', 'structure', 'session_context', 'price_quality', 'freshness'],
  },
  indices: {
    domain: 'indices',
    researchOnly: true,
    productionExecutionAuthority: false,
    requiredEvidence: ['structure', 'session_state', 'context', 'freshness'],
  },
  metals: {
    domain: 'metals',
    researchOnly: true,
    productionExecutionAuthority: false,
    requiredEvidence: ['resolved_instrument', 'structure', 'price_quality', 'context', 'freshness'],
  },
  commodities: {
    domain: 'commodities',
    researchOnly: true,
    productionExecutionAuthority: false,
    requiredEvidence: ['resolved_instrument', 'structure', 'price_quality', 'context', 'freshness'],
  },
};

export function resolveMarketScope(requested?: readonly MarketDomain[]): MarketDomain[] {
  if (!requested || requested.length === 0) return [...ALL_MARKET_DOMAINS];
  const seen = new Set<MarketDomain>();
  const resolved: MarketDomain[] = [];
  for (const domain of requested) {
    if (seen.has(domain)) continue;
    seen.add(domain);
    resolved.push(domain);
  }
  return resolved;
}

export function getMarketProfile(domain: MarketDomain): MarketProfile {
  return PROFILES[domain];
}

function opposite(direction: TradeDirection): TradeDirection {
  return direction === 'LONG' ? 'SHORT' : 'LONG';
}

function addReason(reasons: string[], reason: string): void {
  if (!reasons.includes(reason)) reasons.push(reason);
}

export function challengeCandidate(candidate: OpportunityCandidate): ChallengeResult {
  const reasons: string[] = [];

  if (candidate.freshness === 'STALE' || candidate.freshness === 'UNKNOWN') {
    addReason(reasons, 'FRESHNESS_INSUFFICIENT');
  }
  if (candidate.dataConflict === true) addReason(reasons, 'DATA_CONFLICT');
  if (!candidate.invalidation || candidate.invalidation.trim().length === 0) {
    addReason(reasons, 'INVALIDATION_REQUIRED');
  }

  const staleEvidence = candidate.evidence.some((item) => item.freshness === 'STALE' || item.freshness === 'UNKNOWN');
  if (staleEvidence) addReason(reasons, 'EVIDENCE_FRESHNESS_INSUFFICIENT');

  const noTradeEvidence = candidate.evidence.some((item) => item.direction === 'NO_TRADE' && item.strength > 0);
  if (noTradeEvidence) addReason(reasons, 'NO_TRADE_EVIDENCE');

  const alignedStrength = candidate.evidence
    .filter((item) => item.direction === candidate.direction)
    .reduce((sum, item) => sum + item.strength, 0);
  const opposingDirection = opposite(candidate.direction);
  const opposingStrength = candidate.evidence
    .filter((item) => item.direction === opposingDirection)
    .reduce((sum, item) => sum + item.strength, 0);

  if (alignedStrength <= 0) addReason(reasons, 'ALIGNED_EVIDENCE_REQUIRED');
  if (opposingStrength > 0 && opposingStrength >= alignedStrength) {
    addReason(reasons, 'UNRESOLVED_CONTRADICTION');
  }

  return reasons.length === 0
    ? { status: 'PASS', reasons: [] }
    : { status: 'NO_TRADE', reasons };
}

export function normalizeOpportunityScore(rawScore: number, scale: ScoreScale): number {
  if (!Number.isFinite(rawScore) || !Number.isFinite(scale.min) || !Number.isFinite(scale.max) || scale.max <= scale.min) {
    return 0;
  }
  const ratio = (rawScore - scale.min) / (scale.max - scale.min);
  const clamped = Math.max(0, Math.min(1, ratio));
  return Number((clamped * 100).toFixed(6));
}

export function buildChartContext(candidate: OpportunityCandidate): ChartContext {
  const mapping = candidate.chart;
  if (
    mapping?.provider === 'tradingview'
    && mapping.verified === true
    && mapping.symbol.trim().length > 0
  ) {
    return {
      provider: 'tradingview',
      requestedSymbol: candidate.symbol,
      symbol: mapping.symbol,
      timeframe: mapping.timeframe ?? null,
      mappingStatus: 'VERIFIED',
      navigationHint: { mode: 'VERIFIED_SYMBOL', query: mapping.symbol },
    };
  }
  return {
    provider: 'tradingview',
    requestedSymbol: candidate.symbol,
    symbol: null,
    timeframe: null,
    mappingStatus: 'UNVERIFIED',
    navigationHint: { mode: 'SYMBOL_SEARCH', query: candidate.symbol },
  };
}

export function rankOpportunities(candidates: readonly OpportunityCandidate[]): OpportunityRanking {
  const ranked: RankedOpportunity[] = [];
  const blocked: Array<{ id: string; reasons: string[] }> = [];

  for (const candidate of candidates) {
    const challenge = challengeCandidate(candidate);
    if (challenge.status !== 'PASS') {
      blocked.push({ id: candidate.id, reasons: challenge.reasons });
      continue;
    }
    ranked.push({
      ...candidate,
      normalizedScore: normalizeOpportunityScore(candidate.rawScore, candidate.scoreScale),
      chartContext: buildChartContext(candidate),
    });
  }

  ranked.sort((left, right) => {
    if (right.normalizedScore !== left.normalizedScore) return right.normalizedScore - left.normalizedScore;
    if (right.confidence !== left.confidence) return right.confidence - left.confidence;
    if (right.riskReward !== left.riskReward) return right.riskReward - left.riskReward;
    const symbolOrder = left.symbol.localeCompare(right.symbol);
    if (symbolOrder !== 0) return symbolOrder;
    return left.id.localeCompare(right.id);
  });

  return {
    decision: ranked.length > 0 ? 'TOP_SETUP' : 'NO_TRADE',
    ranked,
    blocked,
  };
}
