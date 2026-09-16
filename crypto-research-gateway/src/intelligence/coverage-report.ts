import type { NormalizedMarketObservation } from './autonomous-scan.js';
import { classifyEvidenceQuality, evidenceMaxAgeMs } from './evidence-quality.js';
import type { MarketDomain } from './multi-market.js';
import type { DataAcquisitionGap } from './source-planner.js';

export type CoverageStatus = 'LIVE' | 'CONTEXT_ONLY' | 'GAP';

export type CoverageReportRecord = {
  domain: MarketDomain;
  requested: true;
  status: CoverageStatus;
  liveObservationCount: number;
  contextObservationCount: number;
  totalObservationCount: number;
  usableObservationCount: number;
  entitlements: string[];
  sources: string[];
  reasons: string[];
};

function pushUnique(target: string[], value: string): void {
  if (!target.includes(value)) target.push(value);
}

function isActionableLiveEvidence(observation: NormalizedMarketObservation): boolean {
  if (observation.timeframe === '15m' || observation.timeframe === '5m') return true;
  return observation.evidenceKind === 'quote'
    || observation.evidenceKind === 'snapshot'
    || observation.evidenceKind === 'trade';
}

export function buildCoverageReport(
  domains: readonly MarketDomain[],
  observations: readonly NormalizedMarketObservation[],
  acquisitionGaps: readonly DataAcquisitionGap[],
  nowMs: number,
): CoverageReportRecord[] {
  return domains.map((domain) => {
    const relevant = observations.filter((item) => item.domain === domain);
    const live: NormalizedMarketObservation[] = [];
    const context: NormalizedMarketObservation[] = [];
    const reasons: string[] = [];

    for (const observation of relevant) {
      const quality = classifyEvidenceQuality(observation, {
        nowMs,
        maxAgeMs: evidenceMaxAgeMs(observation.timeframe),
        clockSkewMs: 5_000,
      });
      for (const reason of quality.reasons) pushUnique(reasons, reason);
      if (quality.liveEligible) {
        live.push(observation);
      } else if (quality.state !== 'INVALID') {
        context.push(observation);
      }
    }

    const planReasons = acquisitionGaps
      .filter((gap) => gap.domain === domain)
      .map((gap) => gap.reason);
    const hasActionableLiveEvidence = live.some(isActionableLiveEvidence);

    let status: CoverageStatus;
    if (hasActionableLiveEvidence) {
      status = 'LIVE';
    } else if (relevant.length > 0) {
      status = 'CONTEXT_ONLY';
      pushUnique(reasons, 'NO_LIVE_EVIDENCE');
    } else {
      status = 'GAP';
      for (const reason of planReasons) pushUnique(reasons, reason);
      if (reasons.length === 0) pushUnique(reasons, 'NO_USABLE_EVIDENCE');
    }

    if (status === 'LIVE') {
      reasons.splice(0, reasons.length);
    }

    return {
      domain,
      requested: true as const,
      status,
      liveObservationCount: live.length,
      contextObservationCount: context.length,
      totalObservationCount: relevant.length,
      usableObservationCount: live.length + context.length,
      entitlements: [...new Set(relevant.map((item) => item.entitlement ?? 'UNVERIFIED'))],
      sources: [...new Set(relevant.map((item) => item.source))],
      reasons,
    };
  });
}
