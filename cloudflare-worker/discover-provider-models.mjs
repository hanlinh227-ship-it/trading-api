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
    if (!res.ok) return { status: res.status, models: [] };
    const body = await res.json();
    const rows = Array.isArray(body?.data) ? body.data : (Array.isArray(body?.models) ? body.models : []);
    return { status: res.status, models: rows.map((m) => String(m?.id || m?.name || '')).filter(Boolean) };
  } catch (err) {
    return { status: err?.name === 'AbortError' ? 0 : 0, models: [] };
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
  const { status, models } = await listOpenAiCompatible(binding.endpoint_url, key);
  const verdict = classify(status);
  console.log(`PROVIDER_DISCOVERY provider=${providerId} status=${verdict} http=${status} models=${models.length}`);
  if (models.length) {
    console.log(`PROVIDER_MODELS provider=${providerId} ids=${JSON.stringify(models.slice(0, MAX_MODELS_SHOWN))}`);
  }
}
