/**
 * Zero-cost TERTIARY research runtime (Netlify Functions).
 *
 * Capacity and failover only. It holds no routing, reasoning or
 * model-selection authority, and the Cloudflare primary never waits on it.
 *
 * It wraps the SAME shared handler the Deno secondary uses, rather than
 * reimplementing the contract. Business logic forked per provider is how two
 * runtimes drift into accepting different inputs, and a tertiary that admits
 * what the primary rejects is a hole shaped like a failover.
 *
 * Deployment status is not asserted here. Whether this is live is a runtime
 * fact only a health probe can establish; the canonical registry records it as
 * ADAPTER_READY with every verification axis false until one does.
 */

import type { Config, Context } from '@netlify/functions';
import { handle } from '../../deno-secondary/main.ts';

const RUNTIME_PROVIDER = 'netlify-functions';
const RUNTIME_ROLE = 'tertiary-capacity-only';

/** Capacity, never authority. Read by the contract test, not decorative. */
const ROUTING_AUTHORITY = false;
const REASONING_AUTHORITY = false;
const MODEL_SELECTION_AUTHORITY = false;

export default async function handler(request: Request, _context: Context): Promise<Response> {
  const response = await handle(request);

  // Re-label the runtime honestly. The shared handler names itself for the
  // runtime it was written for; a tertiary reporting the secondary's identity
  // would make failover evidence unreadable.
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return response;

  let body: Record<string, unknown>;
  try {
    body = await response.json() as Record<string, unknown>;
  } catch {
    return response;
  }
  if (typeof body === 'object' && body !== null && 'runtimeProvider' in body) {
    body.runtimeProvider = RUNTIME_PROVIDER;
    body.runtimeRole = RUNTIME_ROLE;
    if ('routingAuthority' in body) {
      body.routingAuthority = ROUTING_AUTHORITY;
      body.reasoningAuthority = REASONING_AUTHORITY;
      body.modelSelectionAuthority = MODEL_SELECTION_AUTHORITY;
    }
  }
  return new Response(JSON.stringify(body), {
    status: response.status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

export const config: Config = {
  path: ['/health', '/capabilities', '/research/market'],
};
