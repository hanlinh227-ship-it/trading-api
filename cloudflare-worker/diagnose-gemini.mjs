// Advisory, read-only Gemini capability diagnosis.
//
// The previous diagnosis only checked whether the configured model NAME appeared
// in ListModels. That is not sufficient: a model can be listed for an account and
// still reject :generateContent, which surfaces to the mesh probe as a 404
// MODEL_NOT_FOUND. This reports supportedGenerationMethods so the real cause is
// visible, and names listed alternatives that do support generateContent.
//
// Never prints the API key or any response body beyond model metadata.
const KEY = process.env.GEMINI_API_KEY || '';
const BASE = process.env.GEMINI_BASE_URL || 'https://generativelanguage.googleapis.com/v1beta';
const CONFIGURED = process.env.CONFIGURED || '';

if (!KEY || !CONFIGURED) {
  console.log('GEMINI_DIAGNOSIS=SKIPPED reason=not_configured');
  process.exit(0);
}

const listUrl = `${BASE.replace(/\/$/, '')}/models`;
let models = [];
try {
  const res = await fetch(listUrl, { headers: { 'x-goog-api-key': KEY } });
  if (!res.ok) {
    console.log(`GEMINI_DIAGNOSIS=LIST_FAILED status=${res.status}`);
    process.exit(0);
  }
  const data = await res.json();
  models = Array.isArray(data?.models) ? data.models : [];
} catch {
  console.log('GEMINI_DIAGNOSIS=LIST_ERROR');
  process.exit(0);
}

const norm = (n) => String(n || '').replace(/^models\//, '');
const entry = models.find((m) => norm(m.name) === CONFIGURED);
const methods = entry ? (entry.supportedGenerationMethods || []) : null;

console.log(`GEMINI_DIAGNOSIS_LISTED=${entry ? 'yes' : 'no'} configured=${CONFIGURED}`);
if (entry) console.log(`GEMINI_DIAGNOSIS_METHODS=${JSON.stringify(methods)}`);

// Candidates that genuinely support generateContent.
const usable = models
  .filter((m) => (m.supportedGenerationMethods || []).includes('generateContent'))
  .map((m) => norm(m.name))
  .filter((n) => n.startsWith('gemini-'));
console.log(`GEMINI_DIAGNOSIS_GENERATE_CAPABLE=${JSON.stringify(usable.slice(0, 25))}`);

// Live single-shot check against the exact path the Worker adapter builds.
// ListModels metadata is NOT authoritative: a retired model can still be listed
// with generateContent in supportedGenerationMethods and yet return 404. Only a
// real call settles it, so candidates are probed rather than guessed.
async function probeGenerate(model) {
  const url = `${BASE.replace(/\/$/, '')}/models/${encodeURIComponent(model)}:generateContent`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-goog-api-key': KEY },
      body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: 'ping' }] }] }),
    });
    let detail = '';
    if (!res.ok) {
      const body = await res.text();
      // Surface only the provider's own status string, never echoed request data.
      try { detail = String(JSON.parse(body)?.error?.status || '').slice(0, 64); } catch { detail = ''; }
    }
    return { model, status: res.status, reason: detail };
  } catch {
    return { model, status: 0, reason: 'network_error' };
  }
}

const configuredResult = await probeGenerate(CONFIGURED);
console.log(`GEMINI_DIAGNOSIS_GENERATE=status=${configuredResult.status}${configuredResult.reason ? ` reason=${configuredResult.reason}` : ''}`);

// When the configured model cannot generate, find a replacement by PROBING.
// Bounded to a handful of stable flash-class candidates: cheapest free-tier
// class, no preview/experimental, no image/tts/transcribe specialisations.
if (configuredResult.status !== 200) {
  const candidates = usable.filter((n) => (
    n.includes('flash')
    && !n.includes('preview') && !n.includes('exp')
    && !n.includes('image') && !n.includes('tts') && !n.includes('transcribe')
    && n !== CONFIGURED
  )).slice(0, 6);
  const results = [];
  for (const model of candidates) results.push(await probeGenerate(model));
  console.log(`GEMINI_DIAGNOSIS_CANDIDATES=${JSON.stringify(results)}`);
  const winner = results.find((r) => r.status === 200);
  console.log(`GEMINI_DIAGNOSIS_REPLACEMENT=${winner ? winner.model : 'none_generate_capable'}`);
}
