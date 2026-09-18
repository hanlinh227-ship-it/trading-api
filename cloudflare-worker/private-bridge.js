/**
 * The private VPC bridge as an OPTIONAL capability.
 *
 * The canonical primary runtime is public and research-safe. It must not depend
 * on a private VPC resource: when it did, a credential that could not reach the
 * VPC took the whole public runtime down with it (Cloudflare error 10196,
 * "credentials are not authorized for requested VPC resource").
 *
 * So the binding may simply be absent, and that is a NORMAL state rather than a
 * fault. What must never happen is a caller believing the bridge answered when
 * it is not there, so absence is reported as a named state and never emulated.
 */

export const PRIVATE_BRIDGE_AVAILABLE = 'PRIVATE_BRIDGE_AVAILABLE';
export const PRIVATE_BRIDGE_UNAVAILABLE = 'PRIVATE_BRIDGE_UNAVAILABLE';
export const CAPABILITY_TEMPORARILY_UNAVAILABLE = 'CAPABILITY_TEMPORARILY_UNAVAILABLE';

/** Present means a usable binding, not merely a truthy property. */
export function privateBridgeState(env = {}) {
  const binding = env && env.AI_BRIDGE;
  if (!binding || typeof binding.fetch !== 'function') return PRIVATE_BRIDGE_UNAVAILABLE;
  return PRIVATE_BRIDGE_AVAILABLE;
}

export function privateBridgeAvailable(env = {}) {
  return privateBridgeState(env) === PRIVATE_BRIDGE_AVAILABLE;
}

/**
 * The refusal a capability that genuinely needs the bridge should return.
 * Explicit and named: silently emulating private-bridge behaviour on the public
 * runtime would hand back data that looks private-sourced and is not.
 */
export function privateBridgeRefusal(capability = 'private_bridge') {
  return {
    ok: false,
    degraded: true,
    error: CAPABILITY_TEMPORARILY_UNAVAILABLE,
    reason: PRIVATE_BRIDGE_UNAVAILABLE,
    capability,
    detail: 'the AI_BRIDGE binding is not present on this deployment; this capability is optional and is not emulated',
  };
}

/**
 * Transport priority reported honestly. Naming a transport that cannot be used
 * would make health output describe a deployment other than this one.
 */
export function bybitTransportPriority(env = {}) {
  return privateBridgeAvailable(env)
    ? ['cloudflare-vpc-bridge', 'secondary-research-gateway']
    : ['secondary-research-gateway'];
}
