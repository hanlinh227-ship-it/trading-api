import { createHash } from 'node:crypto';

export const DATA_CONTRACT_VERSION = 1 as const;
export const DATA_AUTHORITY_SCOPE = 'research_evidence' as const;
export type DataFreshness = 'FRESH' | 'DEGRADED' | 'STALE' | 'UNKNOWN';

export type DataEnvelope = {
  contract_version: 1;
  kind: string;
  source: string;
  source_sha: string;
  event_time: string;
  ingest_time: string;
  freshness: DataFreshness;
  authority: {
    scope: typeof DATA_AUTHORITY_SCOPE;
    execution: 'none';
  };
  research_only: true;
  production_execution_authority: false;
  provenance: Record<string, unknown>;
  payload: unknown;
  payload_hash: string;
};

function normalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, child]) => [key, normalize(child)]),
    );
  }
  return value;
}

function canonical(value: unknown): string {
  return JSON.stringify(normalize(value));
}

export function computePayloadHash(payload: unknown): string {
  return createHash('sha256').update(canonical(payload), 'utf8').digest('hex');
}

export function buildDataEnvelope(input: {
  kind: string;
  source: string;
  sourceSha: string;
  eventTime: string;
  ingestTime: string;
  freshness: DataFreshness;
  payload: unknown;
  provenance: Record<string, unknown>;
}): DataEnvelope {
  return {
    contract_version: DATA_CONTRACT_VERSION,
    kind: input.kind,
    source: input.source,
    source_sha: input.sourceSha,
    event_time: input.eventTime,
    ingest_time: input.ingestTime,
    freshness: input.freshness,
    authority: { scope: DATA_AUTHORITY_SCOPE, execution: 'none' },
    research_only: true,
    production_execution_authority: false,
    provenance: input.provenance,
    payload: input.payload,
    payload_hash: computePayloadHash(input.payload),
  };
}

export function validateDataEnvelope(payload: unknown): string[] {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return ['ENVELOPE_INVALID'];
  const row = payload as Record<string, unknown>;
  const errors: string[] = [];
  if (row.contract_version !== DATA_CONTRACT_VERSION) errors.push('CONTRACT_VERSION_INVALID');
  if (typeof row.kind !== 'string' || !row.kind) errors.push('KIND_REQUIRED');
  if (typeof row.source !== 'string' || !row.source) errors.push('SOURCE_REQUIRED');
  if (typeof row.source_sha !== 'string' || !row.source_sha) errors.push('SOURCE_SHA_REQUIRED');
  if (!['FRESH', 'DEGRADED', 'STALE', 'UNKNOWN'].includes(String(row.freshness))) errors.push('FRESHNESS_INVALID');

  const eventTime = typeof row.event_time === 'string' ? Date.parse(row.event_time) : Number.NaN;
  const ingestTime = typeof row.ingest_time === 'string' ? Date.parse(row.ingest_time) : Number.NaN;
  if (!Number.isFinite(eventTime)) errors.push('EVENT_TIME_INVALID');
  if (!Number.isFinite(ingestTime)) errors.push('INGEST_TIME_INVALID');
  if (Number.isFinite(eventTime) && Number.isFinite(ingestTime) && eventTime > ingestTime) errors.push('EVENT_AFTER_INGEST');

  const authority = row.authority;
  if (!authority || typeof authority !== 'object' || Array.isArray(authority)) {
    errors.push('AUTHORITY_INVALID');
  } else {
    const auth = authority as Record<string, unknown>;
    if (auth.scope !== DATA_AUTHORITY_SCOPE) errors.push('AUTHORITY_SCOPE_INVALID');
    if (auth.execution !== 'none') errors.push('EXECUTION_AUTHORITY_FORBIDDEN');
  }
  if (row.research_only !== true) errors.push('RESEARCH_ONLY_REQUIRED');
  if (row.production_execution_authority !== false) errors.push('PRODUCTION_EXECUTION_AUTHORITY_FORBIDDEN');
  if (!row.provenance || typeof row.provenance !== 'object' || Array.isArray(row.provenance)) errors.push('PROVENANCE_INVALID');

  if (typeof row.payload_hash !== 'string' || row.payload_hash.length !== 64) {
    errors.push('PAYLOAD_HASH_INVALID');
  } else if (computePayloadHash(row.payload) !== row.payload_hash) {
    errors.push('PAYLOAD_HASH_MISMATCH');
  }
  return errors;
}
