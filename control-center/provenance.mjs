// Where a displayed value came from. The Control Tower is an OBSERVABILITY
// surface: it may show what is known, and it must never let "we did not ask"
// read the same as "we asked and it was fine".
//
// Provenance is derived from an ORIGIN STAMPED BY THIS SERVER at the moment a
// value is obtained - never from the prose of an upstream message. Upstream
// payloads pass through the SAFE_KEYS allowlist, which has no `_origin` key, so
// a source cannot declare its own provenance and cannot upgrade itself to
// REAL_LIVE by saying so.

export const PROVENANCE = Object.freeze({
  REAL_LIVE: 'REAL_LIVE',                     // observed now, within the freshness window
  HISTORICAL_EVIDENCE: 'HISTORICAL_EVIDENCE', // observed, but not now
  CONFIGURED: 'CONFIGURED',                   // settings exist; no runtime state
  NOT_OBSERVED: 'NOT_OBSERVED',               // never asked, or nothing answered
  UNVERIFIED: 'UNVERIFIED',                   // asked, but the answer cannot be dated or established
});

export const PROVENANCE_VALUES = Object.freeze(Object.values(PROVENANCE));

// Origins are the only input. Adding one without adding it here fails closed to
// NOT_OBSERVED rather than inventing a label.
export const ORIGIN = Object.freeze({
  UNCONFIGURED: 'UNCONFIGURED',                       // no URL - nothing was ever asked
  FETCHED: 'FETCHED',                                 // the source answered
  FETCH_FAILED: 'FETCH_FAILED',                       // we asked and the attempt itself is the evidence
  GATEWAY_STATE: 'GATEWAY_STATE',                     // aggregate gateway carried a runtime state
  GATEWAY_METADATA_ONLY: 'GATEWAY_METADATA_ONLY',     // gateway listed it, with no runtime state
  GATEWAY_ABSENT: 'GATEWAY_ABSENT',                   // gateway did not mention it at all
});

// Origins where something actually answered, so freshness decides the label.
const ANSWERED = new Set([ORIGIN.FETCHED, ORIGIN.FETCH_FAILED, ORIGIN.GATEWAY_STATE]);

/**
 * @param {{origin?: string, stale?: boolean, hasTimestamp?: boolean}} facts
 * @returns {string} one of PROVENANCE
 */
export function provenanceFor({ origin, stale, hasTimestamp } = {}) {
  if (origin === ORIGIN.GATEWAY_METADATA_ONLY) return PROVENANCE.CONFIGURED;
  if (!ANSWERED.has(origin)) return PROVENANCE.NOT_OBSERVED;
  // An undatable answer is not history - we cannot establish WHEN it was true,
  // which is a different failure from knowing it is old.
  if (!hasTimestamp) return PROVENANCE.UNVERIFIED;
  return stale ? PROVENANCE.HISTORICAL_EVIDENCE : PROVENANCE.REAL_LIVE;
}

// A provenance that may carry an operational claim forward. NOT_OBSERVED and
// UNVERIFIED never may: they are the absence of evidence, and the Tower must
// not let absence render as health.
const EVIDENTIAL = new Set([PROVENANCE.REAL_LIVE, PROVENANCE.HISTORICAL_EVIDENCE]);
export function isEvidential(provenance) { return EVIDENTIAL.has(provenance); }
