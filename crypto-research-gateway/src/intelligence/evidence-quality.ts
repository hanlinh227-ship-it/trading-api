import type { NormalizedMarketObservation } from './autonomous-scan.js';

export type EvidenceQualityState =
  | 'LIVE_REALTIME'
  | 'DELAYED_CONTEXT'
  | 'STALE'
  | 'UNKNOWN'
  | 'INVALID';

export type EvidenceQualityOptions = {
  nowMs: number;
  maxAgeMs: number;
  clockSkewMs: number;
};

export type EvidenceQualityResult = {
  liveEligible: boolean;
  state: EvidenceQualityState;
  reasons: string[];
};

export function evidenceMaxAgeMs(timeframe: string): number {
  if (timeframe === '5m') return 20 * 60 * 1000;
  if (timeframe === '15m') return 60 * 60 * 1000;
  if (timeframe === '1h') return 4 * 60 * 60 * 1000;
  return 4 * 60 * 60 * 1000;
}

function closedSession(session: string | undefined): boolean {
  if (!session) return false;
  const normalized = session.trim().toLowerCase().replace(/[\s-]+/g, '_');
  return normalized === 'closed' || normalized === 'market_closed' || normalized.endsWith('_closed');
}

function invalid(reasons: string[]): EvidenceQualityResult {
  return { liveEligible: false, state: 'INVALID', reasons };
}

export function classifyEvidenceQuality(
  observation: NormalizedMarketObservation,
  options: EvidenceQualityOptions,
): EvidenceQualityResult {
  const eventMs = Date.parse(observation.eventTime);
  const ingestMs = Date.parse(observation.ingestTime);
  const { nowMs, maxAgeMs, clockSkewMs } = options;

  if (
    !Number.isFinite(eventMs)
    || !Number.isFinite(ingestMs)
    || !Number.isFinite(nowMs)
    || !Number.isFinite(maxAgeMs)
    || !Number.isFinite(clockSkewMs)
    || maxAgeMs < 0
    || clockSkewMs < 0
  ) {
    return invalid(['INVALID_TIMESTAMP_OR_CLOCK']);
  }

  const invalidReasons: string[] = [];
  if (eventMs > nowMs + clockSkewMs) invalidReasons.push('EVENT_TIME_IN_FUTURE');
  if (ingestMs < eventMs - clockSkewMs) invalidReasons.push('INGEST_BEFORE_EVENT');
  if (invalidReasons.length > 0) return invalid(invalidReasons);

  const ageMs = Math.max(0, nowMs - eventMs);
  const isClosed = closedSession(observation.session);

  if (observation.entitlement === 'VERIFIED_DELAYED' || observation.delayClass === 'DELAYED') {
    return {
      liveEligible: false,
      state: 'DELAYED_CONTEXT',
      reasons: ['DELAYED_ENTITLEMENT'],
    };
  }

  if (observation.entitlement !== 'VERIFIED_REALTIME') {
    return {
      liveEligible: false,
      state: 'UNKNOWN',
      reasons: ['ENTITLEMENT_UNVERIFIED'],
    };
  }

  if (observation.delayClass !== 'REALTIME') {
    return {
      liveEligible: false,
      state: 'UNKNOWN',
      reasons: ['DELAY_CLASS_UNVERIFIED'],
    };
  }

  if (observation.freshness === 'UNKNOWN') {
    return {
      liveEligible: false,
      state: 'UNKNOWN',
      reasons: ['FRESHNESS_UNKNOWN'],
    };
  }

  if (isClosed && (ageMs > maxAgeMs || observation.freshness === 'STALE')) {
    return {
      liveEligible: false,
      state: 'DELAYED_CONTEXT',
      reasons: ['MARKET_CLOSED_CONTEXT'],
    };
  }

  if (observation.freshness === 'STALE' || ageMs > maxAgeMs) {
    return {
      liveEligible: false,
      state: 'STALE',
      reasons: ['STALE_EVIDENCE'],
    };
  }

  return { liveEligible: true, state: 'LIVE_REALTIME', reasons: [] };
}
