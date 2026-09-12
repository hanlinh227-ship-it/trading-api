import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchJson } from '../src/providers/http.js';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Web runtime compatibility', () => {
  it('parses provider JSON without requiring the Node Buffer global', async () => {
    vi.stubGlobal('Buffer', undefined);
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ ok: true }),
    })) as unknown as typeof fetch);

    await expect(fetchJson('https://example.test/market')).resolves.toEqual({ ok: true });
  });
});
