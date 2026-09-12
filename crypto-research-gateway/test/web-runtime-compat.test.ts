import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchJson } from '../src/providers/http.js';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Web runtime compatibility', () => {
  it('parses provider JSON without requiring the Node Buffer global', async () => {
    vi.stubGlobal('Buffer', undefined);
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })));

    await expect(fetchJson('https://example.test/market')).resolves.toEqual({ ok: true });
  });
});
