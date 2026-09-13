import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';
import { validateDataEnvelope } from '../src/normalization/data-contract.js';

describe('gateway data boundary contract', () => {
  it('attaches a valid fail-closed dataContract even when providers are unavailable', async () => {
    process.env.DEPLOYMENT_SOURCE_SHA = 'sha-test';
    const app = buildApp({ probeOnStart: false, forceAllProvidersDown: true });
    const response = await app.inject({
      method: 'POST',
      url: '/research/market',
      payload: { action: 'snapshot', symbol: 'BTCUSDT', instrument: 'perpetual' },
    });
    expect(response.statusCode).toBe(503);
    const body = response.json();
    expect(body.dataContract).toBeTruthy();
    expect(body.dataContract.payload.ok).toBe(false);
    expect(body.dataContract.production_execution_authority).toBe(false);
    expect(validateDataEnvelope(body.dataContract)).toEqual([]);
    await app.close();
    delete process.env.DEPLOYMENT_SOURCE_SHA;
  });
});
