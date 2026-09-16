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

function addReason(reasons: string[], reason: string): void {
  if (!reasons.includes(reason)) reasons.push(reason);
}

function sessionRequired(domain: MarketDomain): boolean {
  return domain === 'forex' || domain === 'futures' || domain === 'indices';
}

function contractRequired(domain: MarketDomain): boolean {
  return domain === 'futures' || domain === 'metals' || domain === 'commodities';
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
