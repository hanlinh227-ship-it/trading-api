import { describe, expect, it } from 'vitest';
import { createBybitBridgeFetchJson } from '../../cloudflare-worker/research-bybit-transport.js';
import { BybitProvider } from '../src/providers/bybit.js';

describe('Cloudflare Bybit public VPC transport', () => {
  it('uses the existing AI_BRIDGE with bearer auth and never signs the public request', async () => {
    let seen: Request | null = null;
    const env = {
      BYBIT_VPS_BRIDGE_SECRET: 'bridge-secret',
      AI_BRIDGE: {
        fetch: async (request: Request) => {
          seen = request;
          return new Response(JSON.stringify({
            retCode: 0,
            time: Date.now(),
            result: { list: [{ bid1Price: '100', ask1Price: '101', lastPrice: '100.5', markPrice: '100.4', indexPrice: '100.3' }] },
          }), { status: 200 });
        },
      },
    };
    const fetchJson = createBybitBridgeFetchJson(env);
    const provider = new BybitProvider({ fetchJson });
    const rows = await provider.snapshot('BTCUSDT', 'perpetual');
    expect(rows.find(x => x.priceSemantic === 'bid')?.price).toBe(100);
    expect(rows.find(x => x.priceSemantic === 'ask')?.price).toBe(101);
    expect(seen).not.toBeNull();
    const request = seen as unknown as Request;
    expect(request.url).toContain('/bybit/public/v5/market/tickers?');
    expect(request.headers.get('authorization')).toBe('Bearer bridge-secret');
    expect(request.headers.get('x-bapi-api-key')).toBeNull();
    expect(request.headers.get('x-bapi-sign')).toBeNull();
  });

  it('fails closed for non-Bybit or non-market URLs', async () => {
    const fetchJson = createBybitBridgeFetchJson({
      BYBIT_VPS_BRIDGE_SECRET: 'bridge-secret',
      AI_BRIDGE: { fetch: async () => new Response('{}') },
    });
    await expect(fetchJson('https://evil.example/v5/market/tickers')).rejects.toThrow('scope_violation');
    await expect(fetchJson('https://api.bybit.com/v5/order/realtime')).rejects.toThrow('scope_violation');
  });
});
