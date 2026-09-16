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
import {catalogShape, freeLabel, listedPrice, probeEligibility as catalogProbeEligibility, sanitizeForLog} from './model-mesh/catalog-shape.js';

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
    return { status: res.status, models: rows.map((m) => String(m?.id || m?.name || '')).filter(Boolean), rows, reason: '' };
  } catch (err) {
    // Keep the transport reason. Collapsing every failure to status=0 made a
    // DNS error, a TLS error and a timeout indistinguishable, which is exactly
    // what is needed to tell a wrong endpoint from a slow one. The key travels
    // in a header, never in the URL, so this text cannot carry it.
    const reason = err?.name === 'AbortError'
      ? `timeout_after_${TIMEOUT_MS}ms`
      : String(err?.cause?.code || err?.code || err?.message || 'unknown').slice(0, 120);
    return { status: 0, models: [], rows: [], reason };
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
  const { status, models, rows, reason } = await listOpenAiCompatible(binding.endpoint_url, key);
  const verdict = classify(status);
  const detail = reason ? ` reason=${reason}` : '';
  console.log(`PROVIDER_DISCOVERY provider=${providerId} status=${verdict} http=${status} models=${models.length}${detail} endpoint=${binding.endpoint_url}`);
  if (models.length) {
    const shown = models.slice(0, MAX_MODELS_SHOWN);
    // Say when the list is capped. A truncated list read as a complete one is
    // how a model present in the catalog was reported as absent.
    const truncated = models.length > shown.length ? ` (showing ${shown.length} of ${models.length}; use PROBE_MODEL_ALLOWLIST to target ids beyond the cap)` : '';
    console.log(`PROVIDER_MODELS provider=${providerId} ids=${JSON.stringify(shown)}${truncated}`);
    reportCatalogShape(providerId, rows);
    const labelled = rows.filter((row) => freeLabel(row));
    console.log(`PROVIDER_FREE_LABELS provider=${providerId} labelled=${labelled.length}/${rows.length}` +
      (labelled.length ? ` sample=${JSON.stringify(labelled.slice(0, 8).map((row) => `${row.id || row.name}:${freeLabel(row)}`))}` : ' (catalog exposes no free-tier field)'));
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
    if (res.ok) return { status: res.status };
    // A 401 that says "billing required" and a 401 that says "bad key" call for
    // completely different actions, and the status alone cannot tell them apart.
    let detail = '';
    try {
      const body = await res.text();
      const parsed = (() => { try { return JSON.parse(body); } catch { return null; } })();
      detail = String(parsed?.error?.message || parsed?.message || parsed?.detail || body || '').slice(0, 160);
    } catch { detail = ''; }
    return { status: res.status, detail: sanitizeForLog(detail) };
  } catch (err) {
    const reason = err?.name === 'AbortError' ? `timeout_after_${PROBE_TIMEOUT_MS}ms` : String(err?.cause?.code || err?.code || err?.message || 'unknown').slice(0, 120);
    return { status: 0, reason };
  } finally {
    clearTimeout(timer);
  }
}

// Catalog reading lives in model-mesh/catalog-shape.js so the filters are
// unit-tested rather than trusted; see that file for why each shape is checked.

function reportCatalogShape(providerId, rows) {
  if (!rows.length) return;
  const shape = catalogShape(rows);
  console.log(`PROVIDER_CATALOG_KEYS provider=${providerId} keys=${JSON.stringify(shape.keys)}`);
  console.log(`PROVIDER_CATALOG_SAMPLE provider=${providerId} row=${JSON.stringify(shape.sample)}`);
}

// A completion probe is a real API call. On a mixed catalog that call is
// billable if it lands on a paid model, so a published price above zero is a
// hard skip -- probing it would spend money to discover that it costs money.
// Where the catalog publishes no price, PROBE_ALLOW_UNPRICED decides: default
// on, because most providers publish none and the account itself is free-tier.
const ALLOW_UNPRICED = String(process.env.PROBE_ALLOW_UNPRICED || '1') === '1';

// When the account holder reports a free tier the website shows but the API may
// not, this requires the catalog itself to mark the model free. It is the
// difference between admitting what NVIDIA says is free and admitting whatever
// answered first.
const REQUIRE_FREE_LABEL = String(process.env.PROBE_REQUIRE_FREE_LABEL || '0') === '1';

// Where a provider documents its free models on a pricing page its API does not
// expose, the id list is an INPUT to the probe, never admission evidence. The
// probe intersects it with the live catalog, so an id the vendor lists but the
// catalog has dropped is reported as gone rather than probed blindly, and a
// completion still has to pass before anything is admitted.
const MODEL_ALLOWLIST = (process.env.PROBE_MODEL_ALLOWLIST || '').split(',').map((s) => s.trim()).filter(Boolean);

const probeEligibility = (row) => catalogProbeEligibility(row, { allowUnpriced: ALLOW_UNPRICED, requireFreeLabel: REQUIRE_FREE_LABEL });

// Prefer models the catalog prices at zero, then ids whose name says free.
// A name is a hint for probe ORDER only -- it is never admission evidence, and
// it never overrides a published price.
function orderCandidates(rows) {
  const scored = rows.map((row) => {
    const id = String(row?.id || row?.name || '');
    const price = listedPrice(row);
    const zeroPriced = price !== null && price.input === 0 && price.output === 0;
    const labelled = Boolean(freeLabel(row));
    return { id, row, rank: zeroPriced || labelled ? 0 : (/free|nim|nemotron|mimo|pickle|ling|muse/i.test(id) ? 1 : 2) };
  }).filter((entry) => entry.id);
  return scored.sort((a, b) => a.rank - b.rank).map((entry) => entry);
}

if (String(process.env.PROBE_COMPLETIONS || '') === '1') {
  for (const [providerId, binding] of Object.entries(BINDINGS)) {
    if (only.length && !only.includes(providerId)) continue;
    const key = String(process.env[binding.secret_name] || '').trim();
    if (!key) { console.log(`PROVIDER_PROBE provider=${providerId} verdict=USER_CREDENTIAL_BLOCKED`); continue; }
    if (binding.endpoint_family !== 'openai_compatible') { console.log(`PROVIDER_PROBE provider=${providerId} verdict=SKIPPED_NON_OPENAI_FAMILY family=${binding.endpoint_family}`); continue; }
    const { status: listStatus, models, rows } = await listOpenAiCompatible(binding.endpoint_url, key);
    if (!models.length) { console.log(`PROVIDER_PROBE provider=${providerId} verdict=NO_LISTING http=${listStatus}`); continue; }
    reportCatalogShape(providerId, rows);
    let candidateRows = rows.length ? rows : models.map((id) => ({ id }));
    if (MODEL_ALLOWLIST.length) {
      const present = new Set(models);
      const missing = MODEL_ALLOWLIST.filter((id) => !present.has(id));
      if (missing.length) console.log(`PROVIDER_ALLOWLIST_MISSING provider=${providerId} ids=${JSON.stringify(missing)} (documented but not in the live catalog)`);
      candidateRows = candidateRows.filter((row) => MODEL_ALLOWLIST.includes(String(row?.id || row?.name || '')));
      console.log(`PROVIDER_ALLOWLIST_MATCHED provider=${providerId} matched=${candidateRows.length}/${MODEL_ALLOWLIST.length}`);
      if (!candidateRows.length) { console.log(`PROVIDER_PROBE provider=${providerId} verdict=NO_ALLOWLISTED_MODEL_IN_CATALOG listed=${models.length}`); continue; }
    }
    const ordered = orderCandidates(candidateRows);
    const eligible = [];
    let skippedPaid = 0;
    for (const entry of ordered) {
      const { eligible: ok, note } = probeEligibility(entry.row);
      if (!ok) {
        skippedPaid += 1;
        console.log(`PROVIDER_PROBE_MODEL provider=${providerId} model=${entry.id} verdict=${note}`);
        continue;
      }
      eligible.push(entry.id);
      if (eligible.length >= PROBE_LIMIT) break;
    }
    if (!eligible.length) { console.log(`PROVIDER_PROBE provider=${providerId} verdict=NO_ZERO_PRICE_CANDIDATE listed=${models.length} skipped_paid=${skippedPaid}`); continue; }
    const candidates = eligible;
    let selected = null;
    const attempts = [];
    for (const model of candidates) {
      const { status, reason, detail } = await probeCompletion(binding.endpoint_url, key, model);
      const { verdict, scope } = probeVerdict(status);
      attempts.push(`${model}=${status}`);
      console.log(`PROVIDER_PROBE_MODEL provider=${providerId} model=${model} http=${status} verdict=${verdict}${reason ? ` reason=${reason}` : ''}${detail ? ` detail=${JSON.stringify(detail)}` : ''}`);
      if (status === 200) { selected = model; break; }
      // Only a model-scoped failure justifies trying the provider's next id.
      if (scope !== 'model') break;
    }
    if (selected) {
      console.log(`PROVIDER_PROBE provider=${providerId} verdict=SELECTED model=${selected} probed=${attempts.length} listed=${models.length} skipped_paid=${skippedPaid}`);
    } else {
      // "No live free model found in the probed slice" is a bounded statement,
      // not a claim that the provider has none. Say exactly that.
      console.log(`PROVIDER_PROBE provider=${providerId} verdict=NO_LIVE_CANDIDATE_IN_PROBED_SLICE probed=${attempts.length} listed=${models.length} skipped_paid=${skippedPaid} attempts=${JSON.stringify(attempts)}`);
    }
  }
}
