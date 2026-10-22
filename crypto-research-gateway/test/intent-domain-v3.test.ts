import { describe, expect, it } from 'vitest';
import { resolveDomainsFromIntent, resolveSymbolsFromIntent } from '../src/intelligence/intent-domain.js';
import { buildApp } from '../src/server.js';

describe('V3 natural-language domain intent routing', () => {
  it('resolves forex-only intents', () => {
    expect(resolveDomainsFromIntent('quét forex tìm lệnh tốt nhất')).toEqual(['forex']);
  });

  it('resolves coin/crypto-only intents', () => {
    expect(resolveDomainsFromIntent('quét coin hiện tại')).toEqual(['crypto']);
    expect(resolveDomainsFromIntent('find best crypto setup')).toEqual(['crypto']);
  });

  it('resolves futures-only intents', () => {
    expect(resolveDomainsFromIntent('tìm lệnh futures')).toEqual(['futures']);
  });

  it('resolves explicit multi-market forex coin futures intent', () => {
    expect(resolveDomainsFromIntent('quét đa thị trường forex coin futures')).toEqual(['crypto', 'forex', 'futures']);
  });

  it('leaves ambiguous generic intent unresolved so existing broad-scan fallback remains intact', () => {
    expect(resolveDomainsFromIntent('tìm lệnh tốt nhất hiện tại')).toEqual([]);
  });

  it('infers domains directly from verified instrument tokens', () => {
    expect(resolveDomainsFromIntent('tìm EURUSD')).toEqual(['forex']);
    expect(resolveDomainsFromIntent('tìm BTC')).toEqual(['crypto']);
    expect(resolveDomainsFromIntent('tìm NQ')).toEqual(['futures']);
  });

  it('resolves verified canonical symbols without guessing unknown instruments', () => {
    expect(resolveSymbolsFromIntent('tìm EURUSD forex')).toEqual({ forex: ['EURUSD'] });
    expect(resolveSymbolsFromIntent('tìm BTC coin')).toEqual({ crypto: ['BTCUSDT'] });
    expect(resolveSymbolsFromIntent('tìm NQ futures')).toEqual({ futures: ['NQ'] });
    expect(resolveSymbolsFromIntent('tìm ABCXYZ')).toEqual({});
  });

  it('resolves multiple named instruments across markets in canonical domain order', () => {
    expect(resolveSymbolsFromIntent('quét BTC EURUSD NQ')).toEqual({
      crypto: ['BTCUSDT'],
      forex: ['EURUSD'],
      futures: ['NQ'],
    });
  });

  it('lets autoscan infer requestedDomains from the natural-language intent when omitted', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T12:00:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { intent: 'quét forex tìm lệnh tốt nhất', externalObservations: [] },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().scope).toEqual(['forex']);
    await app.close();
  });

  it('lets autoscan infer a named instrument and narrow the acquisition universe', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T12:00:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { intent: 'tìm setup NQ futures', externalObservations: [] },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.scope).toEqual(['futures']);
    expect(body.dataAcquisitionPlan.symbolsByDomain.futures).toEqual(['NQ']);
    await app.close();
  });

  it('keeps explicit symbols authoritative over symbols inferred from intent', async () => {
    const app = buildApp({ probeOnStart: false, nowMs: Date.parse('2026-09-16T12:00:00.000Z') });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: {
        intent: 'tìm BTC coin',
        requestedDomains: ['crypto'],
        symbols: { crypto: ['ETHUSDT'] },
        externalObservations: [],
      },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().dataAcquisitionPlan.symbolsByDomain.crypto).toEqual(['ETHUSDT']);
    await app.close();
  });
});
