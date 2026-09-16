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

// --- Bounded completion probe-and-select -------------------------------------
//
// A listing proves reachability, never liveness: NVIDIA listed two models that
// answered 410 and 404 on chat completions, and a single hand-picked id then
// stood for the whole provider. This probes a bounded slice of each provider's
// live listing against chat completions and reports the first id that actually
// answers, so admission rests on a completed call instead of a guess.
//
// Read-only with respect to the repository. It prints provider ids, model ids,
// HTTP status and a verdict. Never a key, never a response body.
const PROBE_LIMIT = Math.max(1, Math.min(8, Number(process.env.PROBE_LIMIT || 5)));
const PROBE_TIMEOUT_MS = 20000;

// What a failure says about scope. A model-scoped failure means try the next
// candidate; anything else means the round is over for this provider.
function probeVerdict(status) {
  if (status === 200) return { verdict: 'LIVE_OK', scope: 'provider' };
  if (status === 402) return { verdict: 'BILLABLE_402_MODEL_INELIGIBLE', scope: 'model' };
  if (status === 404) return { verdict: 'MODEL_NOT_FOUND', scope: 'model' };
  if (status === 410) return { verdict: 'MODEL_GONE', scope: 'model' };
  if (status === 400 || status === 422) return { verdict: 'REQUEST_INVALID_FOR_MODEL', scope: 'model' };
  if (status === 401 || status === 403) return { verdict: 'AUTH_OR_SCOPE_FAILED', scope: 'provider' };
  if (status === 429) return { verdict: 'RATE_LIMITED', scope: 'provider' };
  if (status >= 500) return { verdict: 'PROVIDER_SIDE_5XX', scope: 'provider' };
  if (status === 0) return { verdict: 'NETWORK_ERROR', scope: 'provider' };
  return { verdict: `UNEXPECTED_${status}`, scope: 'provider' };
}

async function probeCompletion(url, key, model) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' },
      body: JSON.stringify({ model, max_tokens: 8, messages: [{ role: 'user', content: 'Reply with OK only.' }] }),
      signal: controller.signal,
    });
    return { status: res.status };
  } catch (err) {
    const reason = err?.name === 'AbortError' ? `timeout_after_${PROBE_TIMEOUT_MS}ms` : String(err?.cause?.code || err?.code || err?.message || 'unknown').slice(0, 120);
    return { status: 0, reason };
  } finally {
    clearTimeout(timer);
  }
}

// Prefer ids the provider itself marks free, then ids whose name says free.
// A name is a hint for probe ORDER only -- it is never admission evidence.
function orderCandidates(models) {
  const free = models.filter((id) => /free|nim|nemotron|mimo|pickle|ling|muse/i.test(id));
  const rest = models.filter((id) => !free.includes(id));
  return [...free, ...rest];
}

if (String(process.env.PROBE_COMPLETIONS || '') === '1') {
  for (const [providerId, binding] of Object.entries(BINDINGS)) {
    if (only.length && !only.includes(providerId)) continue;
    const key = String(process.env[binding.secret_name] || '').trim();
    if (!key) { console.log(`PROVIDER_PROBE provider=${providerId} verdict=USER_CREDENTIAL_BLOCKED`); continue; }
    if (binding.endpoint_family !== 'openai_compatible') { console.log(`PROVIDER_PROBE provider=${providerId} verdict=SKIPPED_NON_OPENAI_FAMILY family=${binding.endpoint_family}`); continue; }
    const { status: listStatus, models } = await listOpenAiCompatible(binding.endpoint_url, key);
    if (!models.length) { console.log(`PROVIDER_PROBE provider=${providerId} verdict=NO_LISTING http=${listStatus}`); continue; }
    const candidates = orderCandidates(models).slice(0, PROBE_LIMIT);
    let selected = null;
    const attempts = [];
    for (const model of candidates) {
      const { status, reason } = await probeCompletion(binding.endpoint_url, key, model);
      const { verdict, scope } = probeVerdict(status);
      attempts.push(`${model}=${status}`);
      console.log(`PROVIDER_PROBE_MODEL provider=${providerId} model=${model} http=${status} verdict=${verdict}${reason ? ` reason=${reason}` : ''}`);
      if (status === 200) { selected = model; break; }
      // Only a model-scoped failure justifies trying the provider's next id.
      if (scope !== 'model') break;
    }
    if (selected) {
      console.log(`PROVIDER_PROBE provider=${providerId} verdict=SELECTED model=${selected} probed=${attempts.length} listed=${models.length}`);
    } else {
      // "No live free model found in the probed slice" is a bounded statement,
      // not a claim that the provider has none. Say exactly that.
      console.log(`PROVIDER_PROBE provider=${providerId} verdict=NO_LIVE_CANDIDATE_IN_PROBED_SLICE probed=${attempts.length} listed=${models.length} attempts=${JSON.stringify(attempts)}`);
    }
  }
}
