import { describe, expect, it } from 'vitest';
import { buildDataAcquisitionPlan } from '../src/intelligence/source-planner.js';
import { buildApp } from '../src/server.js';

describe('V3 source operational state is separate from entitlement', () => {
  it('does not route a rate-limited source even when its entitlement is verified realtime', () => {
    const plan = buildDataAcquisitionPlan({
      requestedDomains: ['forex'],
      capabilities: [{
        source: 'fx-live',
        sourceType: 'connector',
        domains: ['forex'],
        entitlement: 'VERIFIED_REALTIME',
        available: true,
        state: 'RATE_LIMITED',
      } as any],
    });

    expect(plan.sourcesByDomain.forex).toBeUndefined();
    expect((plan as any).sourceStateBySource['fx-live']).toBe('RATE_LIMITED');
    expect(plan.entitlementStateBySource['fx-live']).toBe('VERIFIED_REALTIME');
    expect(plan.gaps).toContainEqual({ domain: 'forex', reason: 'SOURCE_RATE_LIMITED' });
  });

  it('accepts explicit source state metadata on the V3 HTTP acquisition context', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        requestedDomains: ['forex'],
        acquisitionContext: {
          sources: [{
            source: 'fx-live',
            sourceType: 'connector',
            domains: ['forex'],
            entitlement: 'VERIFIED_REALTIME',
            available: true,
            state: 'RATE_LIMITED',
          }],
        },
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.dataAcquisitionPlan.sourceStateBySource['fx-live']).toBe('RATE_LIMITED');
    expect(body.dataAcquisitionPlan.gaps).toContainEqual({ domain: 'forex', reason: 'SOURCE_RATE_LIMITED' });
    expect(body.sourceCoverage.forex.status).toBe('GAP');
    await app.close();
  });
});
