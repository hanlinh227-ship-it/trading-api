import { afterEach, describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

afterEach(() => {
  delete process.env.TEST_FAKE_SECRET;
  delete process.env.RAILWAY_GIT_COMMIT_SHA;
  delete process.env.DEPLOYMENT_SOURCE_SHA;
});

describe('HTTP surface', () => {
  it('health never exposes environment secrets', async () => {
    process.env.TEST_FAKE_SECRET = 'do-not-leak';
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(200);
    expect(response.body).not.toContain('do-not-leak');
    await app.close();
  });

  it('health exposes a stable production release marker for connector-managed rollout verification', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(200);
    expect(response.json().deploymentRelease).toBe('live-price-execution-v1');
    await app.close();
  });

  it('health exposes the connector-managed exact source SHA as both source and compatibility commit metadata', async () => {
    process.env.DEPLOYMENT_SOURCE_SHA = 'source-sha-123';
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(200);
    expect(response.json().deploymentSourceSha).toBe('source-sha-123');
    expect(response.json().deploymentCommitSha).toBe('source-sha-123');
    await app.close();
  });

  it('health prefers Railway Git commit metadata when GitHub-triggered metadata exists', async () => {
    process.env.DEPLOYMENT_SOURCE_SHA = 'connector-sha';
    process.env.RAILWAY_GIT_COMMIT_SHA = 'github-sha';
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({ method: 'GET', url: '/health' });
    expect(response.statusCode).toBe(200);
    expect(response.json().deploymentSourceSha).toBe('connector-sha');
    expect(response.json().deploymentCommitSha).toBe('github-sha');
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

  it('requires side for execution_quote requests', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/market',
      payload: {
        action: 'execution_quote',
        symbol: 'BTCUSDT',
        instrument: 'perpetual',
        executionVenue: 'binance',
      },
    });
    expect(response.statusCode).toBe(400);
    await app.close();
  });

  it('accepts the execution_quote schema with an explicit side and fails closed on unavailable venue', async () => {
    const app = buildApp({ probeOnStart: false, forceAllProvidersDown: true });
    const response = await app.inject({
      method: 'POST',
      url: '/research/market',
      payload: {
        action: 'execution_quote',
        symbol: 'BTCUSDT',
        instrument: 'perpetual',
        side: 'LONG',
        executionVenue: 'binance',
      },
    });
    expect(response.statusCode).toBe(503);
    expect(response.json().error).toBe('VENUE_UNAVAILABLE');
    await app.close();
  });
});
