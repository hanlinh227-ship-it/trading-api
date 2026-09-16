import { classifyEvidenceQuality, evidenceMaxAgeMs } from './evidence-quality.js';
import type { NormalizedMarketObservation } from './autonomous-scan.js';
import type { MarketDomain } from './multi-market.js';

export type DomainEvidenceQualitySummary = {
  liveEligible: number;
  contextOnly: number;
  blocked: number;
};

export type DomainEvidenceEvaluation = {
  eligible: boolean;
  reasons: string[];
  selected: NormalizedMarketObservation[];
  qualitySummary: DomainEvidenceQualitySummary;
};

const MATERIAL_PRICE_DIVERGENCE_BPS = 30;

function addReason(reasons: string[], reason: string): void {
  if (!reasons.includes(reason)) reasons.push(reason);
}

function sessionRequired(domain: MarketDomain): boolean {
  return domain === 'forex' || domain === 'futures' || domain === 'indices';
}

function contractRequired(domain: MarketDomain): boolean {
  return domain === 'futures' || domain === 'metals' || domain === 'commodities';
}

function validateInstrumentSemantics(
  observations: readonly NormalizedMarketObservation[],
  reasons: string[],
): void {
  const instrumentTypes = new Set(
    observations
      .map((item) => item.instrumentType)
      .filter((value): value is NonNullable<NormalizedMarketObservation['instrumentType']> => value !== undefined),
  );
  if (instrumentTypes.size > 1) addReason(reasons, 'DATA_CONFLICT');
}

function validateEquivalentBarPrices(
  observations: readonly NormalizedMarketObservation[],
  reasons: string[],
): void {
  const groups = new Map<string, NormalizedMarketObservation[]>();
  for (const observation of observations) {
    if ((observation.evidenceKind ?? 'bar') !== 'bar') continue;
    const key = [
      observation.timeframe,
      observation.eventTime,
      observation.instrumentType ?? 'unknown',
      observation.canonicalSymbol ?? observation.symbol,
    ].join('|');
    const current = groups.get(key) ?? [];
    current.push(observation);
    groups.set(key, current);
  }

  for (const equivalent of groups.values()) {
    if (equivalent.length < 2) continue;
    const closes = equivalent.map((item) => item.close).filter((value) => Number.isFinite(value));
    if (closes.length !== equivalent.length) continue;
    const high = Math.max(...closes);
    const low = Math.min(...closes);
    const reference = (high + low) / 2;
    const divergenceBps = reference > 0
      ? ((high - low) / reference) * 10_000
      : Number.POSITIVE_INFINITY;
    if (divergenceBps > MATERIAL_PRICE_DIVERGENCE_BPS) {
      addReason(reasons, 'DATA_CONFLICT');
      return;
    }
  }
}

function validateContractMetadata(
  observations: readonly NormalizedMarketObservation[],
  nowMs: number,
  reasons: string[],
): void {
  const withContract = observations.filter(
    (item) => item.instrumentType === 'future' && item.providerSymbol && item.contractExpiry,
  );
  if (withContract.length === 0 || withContract.length !== observations.length) {
    addReason(reasons, 'CONTRACT_UNRESOLVED');
    return;
  }

  const providerSymbols = new Set(withContract.map((item) => item.providerSymbol));
  const canonicalSymbols = new Set(withContract.map((item) => item.canonicalSymbol ?? item.symbol));
  const expiryValues = withContract.map((item) => Date.parse(item.contractExpiry as string));
  if (expiryValues.some((value) => !Number.isFinite(value))) {
    addReason(reasons, 'CONTRACT_UNRESOLVED');
    return;
  }
  if (expiryValues.some((value) => value <= nowMs)) {
    addReason(reasons, 'CONTRACT_EXPIRED');
    return;
  }
  if (providerSymbols.size !== 1 || canonicalSymbols.size !== 1) {
    addReason(reasons, 'CONTRACT_UNRESOLVED');
  }
}

export function evaluateDomainEvidence(
  domain: MarketDomain,
  observations: readonly NormalizedMarketObservation[],
  nowMs: number,
): DomainEvidenceEvaluation {
  const reasons: string[] = [];
  const relevant = observations.filter((item) => item.domain === domain);
  const selected: NormalizedMarketObservation[] = [];
  const qualitySummary: DomainEvidenceQualitySummary = {
    liveEligible: 0,
    contextOnly: 0,
    blocked: 0,
  };

  for (const observation of relevant) {
    const quality = classifyEvidenceQuality(observation, {
      nowMs,
      maxAgeMs: evidenceMaxAgeMs(observation.timeframe),
      clockSkewMs: 5_000,
    });
    if (quality.liveEligible) {
      selected.push(observation);
      qualitySummary.liveEligible += 1;
    } else if (quality.state === 'DELAYED_CONTEXT') {
      qualitySummary.contextOnly += 1;
    } else {
      qualitySummary.blocked += 1;
    }
  }

  if (relevant.length === 0) addReason(reasons, 'NO_USABLE_EVIDENCE');
  if (selected.length === 0 && relevant.length > 0) addReason(reasons, 'NO_LIVE_EVIDENCE');

  validateInstrumentSemantics(selected, reasons);
  validateEquivalentBarPrices(selected, reasons);

  const context = selected.filter((item) => item.timeframe === '1h');
  const entry = selected.filter((item) => item.timeframe === '15m');
  const hasEntryEvidence = relevant.some(
    (item) => item.timeframe === '15m' && (item.evidenceKind ?? 'bar') === 'bar',
  );
  if (entry.length === 0 && hasEntryEvidence) addReason(reasons, 'NO_LIVE_EVIDENCE');
  if (context.length === 0) addReason(reasons, 'MISSING_CONTEXT_TIMEFRAME');
  if (entry.length < 3) addReason(reasons, 'MISSING_ENTRY_TIMEFRAME');

  if (sessionRequired(domain) && !selected.some((item) => item.session && item.session.trim().length > 0)) {
    addReason(reasons, 'MISSING_SESSION_CONTEXT');
  }

  if (contractRequired(domain) && selected.length > 0) {
    validateContractMetadata(selected, nowMs, reasons);
  }

  return {
    eligible: reasons.length === 0,
    reasons,
    selected,
    qualitySummary,
  };
}
