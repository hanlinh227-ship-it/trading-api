import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/server.js';

const CASES: Array<{ intent: string; expected: string[] }> = [
  { intent: 'quét forex', expected: ['forex'] },
  { intent: 'tìm lệnh forex', expected: ['forex'] },
  { intent: 'quét coin', expected: ['crypto'] },
  { intent: 'tìm setup crypto', expected: ['crypto'] },
  { intent: 'quét futures', expected: ['futures'] },
  { intent: 'tìm setup NQ futures', expected: ['futures'] },
  { intent: 'quét forex coin future', expected: ['crypto', 'forex', 'futures'] },
  { intent: 'quét forex crypto futures', expected: ['crypto', 'forex', 'futures'] },
];

describe('V3 natural-language market domain routing', () => {
  it.each(CASES)('resolves $intent without caller-supplied requestedDomains', async ({ intent, expected }) => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { intent },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().scope).toEqual(expected);
    await app.close();
  });

  it('keeps broad one-command intent on the approved six-domain scope', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { intent: 'tìm lệnh tốt nhất hiện tại' },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().scope).toEqual(['crypto', 'forex', 'futures', 'indices', 'metals', 'commodities']);
    await app.close();
  });

  it('gives explicit requestedDomains precedence over inferred intent domains', async () => {
    const app = buildApp({ probeOnStart: false });
    const response = await app.inject({
      method: 'POST',
      url: '/research/autoscan',
      payload: { intent: 'quét coin', requestedDomains: ['forex'] },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().scope).toEqual(['forex']);
    await app.close();
  });
});
