// Bounded, read-only provider model discovery and failure classification.
//
// Several bindings have a credential but no admitted model, so no key alone can
// make them LIVE_HEALTHY -- a real model has to be discovered and admitted.
// This lists what each account can actually reach and classifies the outcome,
// so admission decisions rest on evidence instead of a guessed model id.
//
// Read-only. Prints provider ids, model ids, HTTP status and counts. Never a
// key, never an Authorization header, never a response body.
import fs from 'node:fs';

const BINDINGS = JSON.parse(fs.readFileSync('AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json', 'utf8')).bindings;
const MAX_MODELS_SHOWN = 40;
const TIMEOUT_MS = 15000;

// Classify by transport outcome so a missing key is never reported as an
// unhealthy provider, and a rate limit is never reported as a dead one.
function classify(status) {
  if (status === 200) return 'OK';
  if (status === 401) return 'UNAUTHORIZED_BAD_OR_MISSING_KEY';
  if (status === 403) return 'FORBIDDEN_ENTITLEMENT';
  if (status === 404) return 'NOT_FOUND_ENDPOINT_OR_MODEL';
  if (status === 429) return 'RATE_LIMITED';
  if (status >= 500) return 'PROVIDER_SIDE_5XX';
  if (status === 0) return 'NETWORK_ERROR';
  return `UNEXPECTED_${status}`;
}

async function listOpenAiCompatible(url, key) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/models`, {
      headers: { authorization: `Bearer ${key}` },
      signal: controller.signal,
    });
    if (!res.ok) return { status: res.status, models: [], reason: '' };
    const body = await res.json();
    const rows = Array.isArray(body?.data) ? body.data : (Array.isArray(body?.models) ? body.models : []);
    return { status: res.status, models: rows.map((m) => String(m?.id || m?.name || '')).filter(Boolean), reason: '' };
  } catch (err) {
    // Keep the transport reason. Collapsing every failure to status=0 made a
    // DNS error, a TLS error and a timeout indistinguishable, which is exactly
    // what is needed to tell a wrong endpoint from a slow one. The key travels
    // in a header, never in the URL, so this text cannot carry it.
    const reason = err?.name === 'AbortError'
      ? `timeout_after_${TIMEOUT_MS}ms`
      : String(err?.cause?.code || err?.code || err?.message || 'unknown').slice(0, 120);
    return { status: 0, models: [], reason };
  } finally {
    clearTimeout(timer);
  }
}

const only = (process.env.ONLY_PROVIDERS || '').split(',').map((s) => s.trim()).filter(Boolean);

for (const [providerId, binding] of Object.entries(BINDINGS)) {
  if (only.length && !only.includes(providerId)) continue;
  const key = String(process.env[binding.secret_name] || '').trim();
  if (!key) {
    console.log(`PROVIDER_DISCOVERY provider=${providerId} status=USER_CREDENTIAL_BLOCKED secret=${binding.secret_name}`);
    continue;
  }
  if (binding.endpoint_family !== 'openai_compatible') {
    // gemini and cloudflare_ai use native listing shapes handled elsewhere.
    console.log(`PROVIDER_DISCOVERY provider=${providerId} status=SKIPPED_NON_OPENAI_FAMILY family=${binding.endpoint_family}`);
    continue;
  }
  const { status, models, reason } = await listOpenAiCompatible(binding.endpoint_url, key);
  const verdict = classify(status);
  const detail = reason ? ` reason=${reason}` : '';
  console.log(`PROVIDER_DISCOVERY provider=${providerId} status=${verdict} http=${status} models=${models.length}${detail} endpoint=${binding.endpoint_url}`);
  if (models.length) {
    console.log(`PROVIDER_MODELS provider=${providerId} ids=${JSON.stringify(models.slice(0, MAX_MODELS_SHOWN))}`);
  }
}

// --- Entitlement verification ------------------------------------------------
//
// A model listing proves reachability, never that the account's access is
// RECURRING free rather than trial credit or paid. free_only_policy.json turns
// on exactly that distinction, so it must come from evidence, not assumption.
//
// Only some providers expose entitlement to the credential at runtime. Where
// they do, verify it. Where they do not, say so explicitly rather than guess:
// ACCOUNT_ENTITLEMENT_UNAVAILABLE means no runtime endpoint exposes it, and the
// answer has to come from the account holder.
const ENTITLEMENT_PROBES = {
  // HuggingFace exposes the authenticated identity and plan.
  huggingface_inference_providers: async (key) => {
    const res = await fetch('https://huggingface.co/api/whoami-v2', {
      headers: { authorization: `Bearer ${key}` },
    });
    if (!res.ok) return { verdict: 'ENTITLEMENT_PROBE_FAILED', detail: `http=${res.status}` };
    const me = await res.json();
    // Report only plan-shaped fields; never the name, email or token metadata.
    const plan = String(me?.plan || me?.type || 'unknown');
    const isPro = me?.isPro === true;
    const periodEnd = me?.periodEnd ? 'has_billing_period' : 'no_billing_period';
    return {
      verdict: isPro ? 'PAID_OR_PRO_PLAN' : 'NON_PRO_PLAN',
      detail: `plan=${plan} isPro=${isPro} ${periodEnd}`,
    };
  },
};

for (const [providerId, binding] of Object.entries(BINDINGS)) {
  if (only.length && !only.includes(providerId)) continue;
  const key = String(process.env[binding.secret_name] || '').trim();
  if (!key) {
    console.log(`PROVIDER_ENTITLEMENT provider=${providerId} verdict=USER_CREDENTIAL_BLOCKED`);
    continue;
  }
  const probe = ENTITLEMENT_PROBES[providerId];
  if (!probe) {
    console.log(`PROVIDER_ENTITLEMENT provider=${providerId} verdict=ACCOUNT_ENTITLEMENT_UNAVAILABLE detail=no_runtime_entitlement_endpoint`);
    continue;
  }
  try {
    const { verdict, detail } = await probe(key);
    console.log(`PROVIDER_ENTITLEMENT provider=${providerId} verdict=${verdict} detail=${detail}`);
  } catch (err) {
    const reason = String(err?.cause?.code || err?.code || err?.message || 'unknown').slice(0, 80);
    console.log(`PROVIDER_ENTITLEMENT provider=${providerId} verdict=ENTITLEMENT_PROBE_ERROR detail=${reason}`);
  }
}
