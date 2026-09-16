import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

function legacyFreshObservations() {
  return [
    {
      id: 'legacy-1', domain: 'forex', symbol: 'EURUSD', source: 'legacy-feed', sourceType: 'connector',
      eventTime: '2026-09-16T06:00:00.000Z', ingestTime: '2026-09-16T08:00:01.000Z', freshness: 'FRESH', timeframe: '1h',
      open: 1.176, high: 1.18, low: 1.175, close: 1.179, bid: 1.1789, ask: 1.1791,
    },
    {
      id: 'legacy-2', domain: 'forex', symbol: 'EURUSD', source: 'legacy-feed', sourceType: 'connector',
      eventTime: '2026-09-16T07:00:00.000Z', ingestTime: '2026-09-16T08:00:01.000Z', freshness: 'FRESH', timeframe: '1h',
      open: 1.179, high: 1.183, low: 1.178, close: 1.182, bid: 1.1819, ask: 1.1821,
    },
    {
      id: 'legacy-3', domain: 'forex', symbol: 'EURUSD', source: 'legacy-feed', sourceType: 'connector',
      eventTime: '2026-09-16T08:00:00.000Z', ingestTime: '2026-09-16T08:00:01.000Z', freshness: 'FRESH', timeframe: '1h',
      open: 1.182, high: 1.186, low: 1.181, close: 1.185, bid: 1.1849, ask: 1.1851,
    },
  ];
}

describe('autoscan V2 backward compatibility after V3 rollout', () => {
  it('does not mark a covered legacy TOP_SETUP degraded solely because V3 acquisition context is absent', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        requestedDomains: ['forex'],
        externalObservations: legacyFreshObservations(),
        maxResults: 1,
      },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.decision).toBe('TOP_SETUP');
    expect(body.coverage[0].status).toBe('COVERED');
    expect(body.degraded).toBe(false);
    await app.close();
  });
});
