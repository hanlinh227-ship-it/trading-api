import { describe, expect, it } from 'vitest';
import { resolveDomainsFromIntent } from '../src/intelligence/intent-domain.js';
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
});
