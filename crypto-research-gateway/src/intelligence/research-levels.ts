import type { NormalizedMarketObservation } from './autonomous-scan.js';
import type { TradeDirection } from './multi-market.js';

export type ResearchEntrySemantic = 'EXECUTABLE_ASK' | 'EXECUTABLE_BID' | 'REFERENCE_CLOSE';

export type ResearchLevels = {
  entry: number;
  entrySemantic: ResearchEntrySemantic;
  stop: number;
  target: number;
  riskReward: number;
  invalidationBasis: string;
  researchOnly: true;
};

export type BuildResearchLevelsInput = {
  direction: TradeDirection;
  observations: readonly NormalizedMarketObservation[];
  structuralStop: number;
  riskReward: number;
  invalidationBasis: string;
};

export type BuildResearchLevelsResult = {
  levels?: ResearchLevels;
  blockedReason?: 'INVALID_RISK_GEOMETRY' | 'NO_PRICE_REFERENCE';
};

function cleanNumber(value: number): number {
  return Number(value.toFixed(12));
}

function newestFirst(observations: readonly NormalizedMarketObservation[]): NormalizedMarketObservation[] {
  return observations
    .filter((item) => Number.isFinite(Date.parse(item.eventTime)))
    .slice()
    .sort((left, right) => Date.parse(right.eventTime) - Date.parse(left.eventTime));
}

function executablePrice(
  direction: TradeDirection,
  observations: readonly NormalizedMarketObservation[],
): { entry: number; semantic: ResearchEntrySemantic } | null {
  for (const observation of newestFirst(observations)) {
    const verifiedRealtime = observation.entitlement === 'VERIFIED_REALTIME'
      && observation.delayClass === 'REALTIME';
    if (!verifiedRealtime) continue;

    if (direction === 'LONG' && observation.ask !== undefined && Number.isFinite(observation.ask)) {
      return { entry: observation.ask, semantic: 'EXECUTABLE_ASK' };
    }
    if (direction === 'SHORT' && observation.bid !== undefined && Number.isFinite(observation.bid)) {
      return { entry: observation.bid, semantic: 'EXECUTABLE_BID' };
    }
  }
  return null;
}

function referenceClose(
  observations: readonly NormalizedMarketObservation[],
): { entry: number; semantic: 'REFERENCE_CLOSE' } | null {
  for (const observation of newestFirst(observations)) {
    if (Number.isFinite(observation.close)) {
      return { entry: observation.close, semantic: 'REFERENCE_CLOSE' };
    }
  }
  return null;
}

export function buildResearchLevels(input: BuildResearchLevelsInput): BuildResearchLevelsResult {
  if (
    !Number.isFinite(input.structuralStop)
    || !Number.isFinite(input.riskReward)
    || input.riskReward <= 0
    || input.invalidationBasis.trim().length === 0
  ) {
    return { blockedReason: 'INVALID_RISK_GEOMETRY' };
  }

  const price = executablePrice(input.direction, input.observations) ?? referenceClose(input.observations);
  if (!price || !Number.isFinite(price.entry)) {
    return { blockedReason: 'NO_PRICE_REFERENCE' };
  }

  const risk = input.direction === 'LONG'
    ? price.entry - input.structuralStop
    : input.structuralStop - price.entry;
  if (!Number.isFinite(risk) || risk <= 0) {
    return { blockedReason: 'INVALID_RISK_GEOMETRY' };
  }

  const target = input.direction === 'LONG'
    ? price.entry + risk * input.riskReward
    : price.entry - risk * input.riskReward;
  if (!Number.isFinite(target)) {
    return { blockedReason: 'INVALID_RISK_GEOMETRY' };
  }

  return {
    levels: {
      entry: cleanNumber(price.entry),
      entrySemantic: price.semantic,
      stop: cleanNumber(input.structuralStop),
      target: cleanNumber(target),
      riskReward: input.riskReward,
      invalidationBasis: input.invalidationBasis,
      researchOnly: true,
    },
  };
}
