// Bounded, read-only Model Mesh health maintenance on the Worker's own cron.
//
// Live provider evidence expires after LIVE_TTL_MS (30 min). The external
// GitHub Actions schedule cannot keep inside that window: over 4.9 hours with
// a fixed-minute 20-minute cadence live on main, exactly one scheduled run
// fired. Cloudflare's scheduler is not subject to that load shedding, runs
// cloud-side with no laptop involved, and already has the provider bindings.
//
// This handler is deliberately the narrowest thing that closes that gap. It
// refreshes provider health evidence and does nothing else. It never places an
// order, never touches wallet, account or live-trading switches, never
// deploys, never mutates routing or Brain authority, and never calls a paid
// provider -- provider selection stays FREE_ONLY inside the canonical probe.
import {claimSelfHeal} from './self-heal.js';

// Cloudflare fires this reliably, so a 20-minute cadence keeps evidence fresh
// with margin inside the 30-minute TTL.
export const HEALTH_REFRESH_CRON = '*/20 * * * *';

// The intents this handler must never acquire are asserted against this file's
// own source by test-scheduled-health.mjs, which owns that list so this module
// never has to name the things it is forbidden to touch.

/**
 * Reject any cron the Worker is not explicitly allowed to carry.
 * The rule is semantic: a read-only health-maintenance cron is permitted, and
 * every other cron -- financial, autonomous or merely unexplained -- is not.
 */
export function assertHealthOnlyCrons(crons) {
  const list = Array.isArray(crons) ? crons : [];
  for (const cron of list) {
    if (String(cron) !== HEALTH_REFRESH_CRON) {
      throw new Error(`unexpected_cron: ${cron}. Only the bounded Model Mesh health refresh may run on a Worker cron.`);
    }
  }
  return true;
}

/**
 * Run one bounded health refresh for a scheduled event.
 *
 * Fails closed on an unrecognised cron, shares the self-heal KV lock so a
 * request-triggered probe and this cron can never probe concurrently, and
 * isolates provider failures: a provider outage must not surface as a failed
 * scheduled invocation.
 */
export async function handleScheduledHealthRefresh({event, env, ctx, probeProviders, modelSnapshot, nowMs = Date.now()} = {}) {
  if (String(event?.cron || '') !== HEALTH_REFRESH_CRON) return {ran: false, reason: 'unexpected_cron'};
  if (typeof probeProviders !== 'function') return {ran: false, reason: 'probe_not_configured'};

  // Sharing the self-heal lock key is deliberate: it is the same work, so the
  // manual and scheduled paths must contend for the same claim.
  const claim = await claimSelfHeal(env?.TRADING_STATE, {nowMs});
  if (!claim.claimed) return {ran: false, reason: claim.reason};

  const work = (async () => {
    try {
      await probeProviders(env, {modelSnapshot});
    } catch {
      // Isolated on purpose: a provider being down is a health observation,
      // not a runtime failure, and must never mark the invocation failed.
    }
  })();

  if (typeof ctx?.waitUntil === 'function') ctx.waitUntil(work); else await work;
  return {ran: true};
}
