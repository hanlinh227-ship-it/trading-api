/**
 * Zero-cost SECONDARY research runtime (Deno Deploy).
 *
 * This is runtime capacity and failover only. It holds none of the six
 * authorities: it does not route, reason, select models, or decide anything.
 * GITHUB_BRAIN_V4 -> task_router -> Model Mesh remain the single authorities,
 * and nothing here may become a second copy of any of them.
 *
 * It serves the SAME contract as the Cloudflare primary - /health,
 * /capabilities, /research/market - over the same shared ResearchRuntime, so a
 * caller cannot tell which runtime answered except by the honest
 * `runtimeProvider` and `runtimeRole` fields.
 *
 * Deployment status is not asserted here. Whether this is actually live is a
 * runtime fact that only a health probe can establish, and the canonical
 * contract records it as `deployed: false, health_verified: false` until one
 * does. Running this file locally proves nothing about production.
 */

import { ResearchRuntime } from '../crypto-research-gateway/src/research.ts';
import { buildDataEnvelope } from '../crypto-research-gateway/src/normalization/data-contract.ts';
import type { DataFreshness } from '../crypto-research-gateway/src/normalization/data-contract.ts';

const SERVICE_NAME = 'crypto-research-gateway';
const SERVICE_VERSION = '0.1.0';
const RUNTIME_MODE = 'zero-local-research-safe';
const DEPLOYMENT_RELEASE = 'live-price-execution-v1';
const RUNTIME_PROVIDER = 'deno-deploy';

/** Capacity, never authority. Read by the contract test, not decorative. */
const RUNTIME_ROLE = 'secondary-capacity-only';
const ROUTING_AUTHORITY = false;
const REASONING_AUTHORITY = false;
const MODEL_SELECTION_AUTHORITY = false;

const MAX_BODY_BYTES = 256_000;
const ACTIONS = new Set(['snapshot', 'candles', 'orderbook', 'funding_oi', 'execution_quote']);
const INSTRUMENTS = new Set(['spot', 'perpetual']);
const SIDES = new Set(['LONG', 'SHORT']);
const EXECUTION_VENUES = new Set(['bybit', 'binance']);
const BYBIT_DEMO_BASE = 'https://api-demo.bybit.com';
const BYBIT_PRIVATE_PATHS = new Set([
  '/v5/account/wallet-balance',
  '/v5/position/list',
  '/v5/order/realtime',
  '/v5/position/closed-pnl',
  '/v5/order/create',
  '/v5/order/amend',
  '/v5/order/cancel',
  '/v5/order/cancel-all',
  '/v5/position/set-leverage',
  '/v5/position/trading-stop',
]);
const MARKET_TOOLS = [
  'market_snapshot',
  'market_candles',
  'market_orderbook',
  'market_execution_quote',
  'derivatives_funding_oi',
];
const ALLOWED_KEYS = new Set([
  'action', 'symbol', 'instrument', 'preferredVenue',
  'interval', 'limit', 'side', 'executionVenue',
]);

const runtime = new ResearchRuntime();
const encoder = new TextEncoder();

function sourceSha(): string {
  // Provider-neutral: the same variable name the primary uses. No Deno-specific
  // deployment id is treated as the source of truth.
  return Deno.env.get('DEPLOYMENT_SOURCE_SHA') ?? Deno.env.get('RUNTIME_REVISION') ?? '';
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

function validOptionalString(value: unknown, min: number, max: number): boolean {
  return value === undefined || (typeof value === 'string' && value.length >= min && value.length <= max);
}

/** Identical admission rules to the primary. A laxer secondary would be a way
 *  to get a stricter runtime's guarantees without its checks. */
function parseMarketInput(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  if (Object.keys(raw).some((key) => !ALLOWED_KEYS.has(key))) return null;
  if (typeof raw.action !== 'string' || !ACTIONS.has(raw.action)) return null;
  if (typeof raw.symbol !== 'string' || raw.symbol.length < 3 || raw.symbol.length > 40) return null;
  const instrument = raw.instrument === undefined ? 'spot' : raw.instrument;
  if (typeof instrument !== 'string' || !INSTRUMENTS.has(instrument)) return null;
  if (!validOptionalString(raw.preferredVenue, 2, 20)) return null;
  if (!validOptionalString(raw.interval, 1, 12)) return null;
  if (raw.limit !== undefined && (!Number.isInteger(raw.limit) || (raw.limit as number) < 1 || (raw.limit as number) > 500)) return null;
  if (raw.side !== undefined && (typeof raw.side !== 'string' || !SIDES.has(raw.side))) return null;
  if (raw.executionVenue !== undefined && (typeof raw.executionVenue !== 'string' || !EXECUTION_VENUES.has(raw.executionVenue))) return null;
  if (raw.action === 'execution_quote' && !raw.side) return null;
  return {
    action: raw.action,
    symbol: (raw.symbol as string).toUpperCase(),
    instrument,
    ...(raw.preferredVenue === undefined ? {} : { preferredVenue: raw.preferredVenue }),
    ...(raw.interval === undefined ? {} : { interval: raw.interval }),
    ...(raw.limit === undefined ? {} : { limit: raw.limit }),
    ...(raw.side === undefined ? {} : { side: raw.side }),
    ...(raw.executionVenue === undefined ? {} : { executionVenue: raw.executionVenue }),
  };
}

function freshnessFor(result: Record<string, unknown>): DataFreshness {
  if (result?.ok !== true) return 'UNKNOWN';
  return result?.degraded === true ? 'DEGRADED' : 'FRESH';
}

function withDataContract(result: Record<string, unknown>, nowMs: number): Record<string, unknown> {
  const body = { ...result };
  delete body.dataContract;
  const dataContract = buildDataEnvelope({
    kind: 'crypto_market_research_edge',
    source: 'deno-research-gateway',
    sourceSha: sourceSha() || 'UNKNOWN',
    eventTime: new Date(nowMs).toISOString(),
    ingestTime: new Date(nowMs).toISOString(),
    freshness: freshnessFor(body),
    payload: body,
    provenance: { runtime: RUNTIME_PROVIDER, role: RUNTIME_ROLE },
  });
  return { ...body, dataContract };
}

export async function handle(request: Request): Promise<Response> {
  const url = new URL(request.url);

  if (url.pathname === '/health') {
    if (request.method !== 'GET') return json({ ok: false, error: 'method_not_allowed' }, 405);
    await runtime.probeAll().catch(() => undefined);
    const providers = runtime.getHealth() as Record<string, { ok?: boolean }>;
    return json({
      ok: true,
      service: SERVICE_NAME,
      version: SERVICE_VERSION,
      runtimeMode: RUNTIME_MODE,
      runtimeProvider: RUNTIME_PROVIDER,
      runtimeRole: RUNTIME_ROLE,
      routingAuthority: ROUTING_AUTHORITY,
      reasoningAuthority: REASONING_AUTHORITY,
      modelSelectionAuthority: MODEL_SELECTION_AUTHORITY,
      deploymentRelease: DEPLOYMENT_RELEASE,
      deploymentSourceSha: sourceSha(),
      localInstallRequired: false,
      lastPublicProbeTimestamp: runtime.getLastProbeAt(),
      healthyProviders: Object.entries(providers).filter(([, s]) => s?.ok === true).map(([id]) => id),
      degradedProviders: Object.entries(providers).filter(([, s]) => s?.ok !== true).map(([id]) => id),
      providers,
    });
  }

  if (url.pathname === '/capabilities') {
    if (request.method !== 'GET') return json({ ok: false, error: 'method_not_allowed' }, 405);
    return json({
      service: SERVICE_NAME,
      version: SERVICE_VERSION,
      runtimeMode: RUNTIME_MODE,
      runtimeProvider: RUNTIME_PROVIDER,
      runtimeRole: RUNTIME_ROLE,
      localInstallRequired: false,
      tools: MARKET_TOOLS,
    });
  }

  if (url.pathname === '/bybit/private-egress') {
    if (request.method !== 'POST') return json({ ok: false, error: 'method_not_allowed' }, 405);
    const expected = Deno.env.get('BYBIT_DEMO_EGRESS_SHARED_SECRET') ?? '';
    const supplied = request.headers.get('authorization') ?? '';
    if (!expected || supplied !== 'Bearer ' + expected) return json({ ok: false, error: 'unauthorized' }, 401);

    let raw: Record<string, unknown>;
    try {
      const text = await request.text();
      if (encoder.encode(text).byteLength > 64_000) throw new Error('body_too_large');
      raw = JSON.parse(text);
    } catch {
      return json({ ok: false, error: 'invalid_egress_request' }, 400);
    }

    const method = String(raw.method ?? '').toUpperCase();
    const path = String(raw.path ?? '');
    const query = String(raw.query ?? '');
    const body = String(raw.body ?? '');
    const headers = raw.headers && typeof raw.headers === 'object' && !Array.isArray(raw.headers)
      ? raw.headers as Record<string, string>
      : null;

    if (!['GET', 'POST'].includes(method) || !BYBIT_PRIVATE_PATHS.has(path) || !headers) {
      return json({ ok: false, error: 'egress_request_not_allowed' }, 400);
    }

    const forwardedHeaders = new Headers();
    for (const key of ['X-BAPI-API-KEY', 'X-BAPI-TIMESTAMP', 'X-BAPI-RECV-WINDOW', 'X-BAPI-SIGN', 'Content-Type', 'Accept', 'X-Trading-Runtime-Contract']) {
      const value = headers[key] ?? headers[key.toLowerCase()];
      if (value) forwardedHeaders.set(key, String(value));
    }
    if (!forwardedHeaders.get('X-BAPI-API-KEY') || !forwardedHeaders.get('X-BAPI-SIGN') || !forwardedHeaders.get('X-BAPI-TIMESTAMP')) {
      return json({ ok: false, error: 'missing_signed_headers' }, 400);
    }

    const target = BYBIT_DEMO_BASE + path + (method === 'GET' && query ? '?' + query : '');
    try {
      const upstream = await fetch(target, {
        method,
        headers: forwardedHeaders,
        body: method === 'GET' ? undefined : body,
        signal: AbortSignal.timeout(25_000),
      });
      const text = await upstream.text();
      let parsed: unknown = null;
      try { parsed = text ? JSON.parse(text) : null; } catch { parsed = null; }
      if (!parsed || typeof parsed !== 'object') {
        return json({ ok: false, error: 'invalid_bybit_response', httpStatus: upstream.status }, 502);
      }
      return json({ ok: upstream.ok, httpStatus: upstream.status, upstream: parsed }, upstream.ok ? 200 : upstream.status);
    } catch (error) {
      return json({ ok: false, error: 'bybit_demo_egress_fetch_failed', detail: String(error?.message ?? error).slice(0, 180) }, 502);
    }
  }

  if (url.pathname === '/research/market') {
    if (request.method !== 'POST') return json({ ok: false, error: 'method_not_allowed' }, 405);
    let raw: unknown;
    try {
      const text = await request.text();
      if (encoder.encode(text).byteLength > MAX_BODY_BYTES) throw new Error('body_too_large');
      raw = JSON.parse(text);
    } catch {
      return json({ ok: false, degraded: false, error: 'invalid_research_request' }, 400);
    }
    const input = parseMarketInput(raw);
    if (!input) return json({ ok: false, degraded: false, error: 'invalid_research_request' }, 400);
    const result = await runtime.runMarket(input as never) as Record<string, unknown>;
    const body = withDataContract(result, Date.now());
    return json(body, result?.degraded === true && result?.ok === false ? 503 : 200);
  }

  return json({ ok: false, error: 'not_found' }, 404);
}

if (import.meta.main) {
  Deno.serve(handle);
}
