import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

describe('HTTP surface', () => {
  it('health never exposes environment secrets', async () => {
    process.env.TEST_FAKE_SECRET = 'do-not-leak';
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(200);
    expect(response.body).not.toContain('do-not-leak');
    await app.close();
  });

  it('capabilities expose read-only tools only', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({ method: 'GET', url: '/capabilities' });
    const body = response.json();
    expect(response.statusCode).toBe(200);
    expect(JSON.stringify(body)).not.toMatch(/place_order|withdraw|transfer|swap|bridge|wallet|payment/i);
    await app.close();
  });

  it('rejects a high-risk research action', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/market',
      payload: { action: 'place_order', symbol: 'BTCUSDT' },
    });
    expect([400, 403]).toContain(response.statusCode);
    await app.close();
  });

  it('returns an explicit degraded response when no provider is healthy', async () => {
    const app = buildApp({ probeOnStart: false, forceAllProvidersDown: true });
    const response = await app.inject({
      method: 'POST',
      url: '/research/market',
      payload: { action: 'snapshot', symbol: 'BTCUSDT', instrument: 'spot' },
    });
    expect(response.statusCode).toBe(503);
    expect(response.json().degraded).toBe(true);
    await app.close();
  });
});
