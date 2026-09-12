import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchJson } from '../src/providers/http.js';
import { normalizeProviderSymbol } from '../src/providers/index.js';

afterEach(() => vi.restoreAllMocks());

describe('provider safety helpers', () => {
  it('normalizes venue-specific spot symbols', () => {
    expect(normalizeProviderSymbol('binance', 'BTC-USDT', 'spot')).toBe('BTCUSDT');
    expect(normalizeProviderSymbol('okx', 'BTCUSDT', 'spot')).toBe('BTC-USDT');
    expect(normalizeProviderSymbol('gate', 'BTCUSDT', 'spot')).toBe('BTC_USDT');
    expect(normalizeProviderSymbol('kucoin', 'BTCUSDT', 'spot')).toBe('BTC-USDT');
  });

  it('uses GET only and does not add authorization headers', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    await fetchJson('https://example.test/public');
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe('GET');
    expect(new Headers(init?.headers).has('authorization')).toBe(false);
  });

  it('throws on non-2xx provider responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('down', { status: 503 }));
    await expect(fetchJson('https://example.test/public')).rejects.toThrow(/503/);
  });
});
