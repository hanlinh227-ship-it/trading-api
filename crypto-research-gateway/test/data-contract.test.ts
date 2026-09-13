import { describe, expect, it } from 'vitest';
import { buildDataEnvelope, validateDataEnvelope } from '../src/normalization/data-contract.js';

function baseEnvelope() {
  return buildDataEnvelope({
    kind: 'market_snapshot',
    source: 'crypto-research-gateway',
    sourceSha: 'abc123',
    eventTime: '2026-09-13T17:30:00.000Z',
    ingestTime: '2026-09-13T17:30:00.250Z',
    freshness: 'FRESH',
    payload: { symbol: 'BTCUSDT', last: 77000 },
    provenance: { price: { provider: 'bybit', sourceTimestampMs: 1 } },
  });
}

describe('canonical trading data envelope', () => {
  it('is research-only and hash verified', () => {
    const payload = baseEnvelope();
    expect(payload.contract_version).toBe(1);
    expect(payload.authority.scope).toBe('research_evidence');
    expect(payload.authority.execution).toBe('none');
    expect(payload.production_execution_authority).toBe(false);
    expect(validateDataEnvelope(payload)).toEqual([]);
  });

  it('rejects tampering and authority escalation', () => {
    const payload = baseEnvelope();
    payload.payload = { symbol: 'BTCUSDT', last: 1 };
    expect(validateDataEnvelope(payload)).toContain('PAYLOAD_HASH_MISMATCH');

    const escalation = baseEnvelope();
    escalation.authority.execution = 'trade' as never;
    escalation.production_execution_authority = true;
    const errors = validateDataEnvelope(escalation);
    expect(errors).toContain('EXECUTION_AUTHORITY_FORBIDDEN');
    expect(errors).toContain('PRODUCTION_EXECUTION_AUTHORITY_FORBIDDEN');
  });

  it('rejects event times after ingest times', () => {
    const payload = baseEnvelope();
    payload.event_time = '2026-09-13T17:31:00.000Z';
    payload.ingest_time = '2026-09-13T17:30:00.000Z';
    expect(validateDataEnvelope(payload)).toContain('EVENT_AFTER_INGEST');
  });
});
