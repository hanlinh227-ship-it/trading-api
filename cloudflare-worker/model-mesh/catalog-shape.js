// Reading a provider's model catalog without guessing its schema.
//
// SambaNova publishes a price per model; NVIDIA and Zen appeared not to. But
// "appeared not to" was a guess until the row shape was read, and guessing a
// field name is the same mistake as guessing a model id. These helpers check
// the shapes a catalog plausibly uses, report which one matched, and fail
// closed when none does: an absent label reads as "not free", never as free.
//
// Catalog metadata is public, but rows are redacted and truncated before they
// are logged. Nothing here is worth leaking a credential over.

const SECRET_SHAPE = /(?:sk-|AIza|hf_|nvapi-|Bearer\s)[A-Za-z0-9_-]{6,}/g;

export function sanitizeForLog(value, depth = 0) {
  if (value === null || value === undefined) return value;
  if (typeof value === 'string') return value.replace(SECRET_SHAPE, '[REDACTED]').slice(0, 120);
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (depth >= 2) return '[nested]';
  if (Array.isArray(value)) return value.slice(0, 6).map((item) => sanitizeForLog(item, depth + 1));
  if (typeof value === 'object') {
    const out = {};
    for (const [key, item] of Object.entries(value).slice(0, 20)) out[key] = sanitizeForLog(item, depth + 1);
    return out;
  }
  return String(value).slice(0, 60);
}

export const FREE_LABEL_FIELDS = Object.freeze([
  'free', 'is_free', 'isFree', 'free_endpoint', 'freeEndpoint', 'tier', 'plan', 'access',
  'access_tier', 'accessTier', 'pricing_tier', 'category', 'label', 'labels', 'tags',
  'endpoint_type', 'availability',
]);

/** The provider's own free marking, or null when the catalog carries none. */
export function freeLabel(row) {
  if (!row || typeof row !== 'object') return null;
  for (const field of FREE_LABEL_FIELDS) {
    const value = row[field];
    if (value === undefined || value === null) continue;
    if (value === true) return `${field}=true`;
    const text = Array.isArray(value) ? value.join(',') : String(value);
    // The word free, not the letters: "freelancer-pro" is not a free tier.
    if (/\bfree\b|free[_-]?endpoint|free[_-]?tier/i.test(text)) return `${field}=${text.slice(0, 60)}`;
  }
  return null;
}

/** A listed model's price, or null when the catalog publishes none for it. */
export function listedPrice(row) {
  if (!row || typeof row !== 'object') return null;
  const cost = (typeof row.cost === 'object' && row.cost) || (typeof row.pricing === 'object' && row.pricing) || {};
  const read = (...keys) => {
    for (const key of keys) {
      const value = cost?.[key] ?? row?.[key];
      if (value === null || value === undefined || typeof value === 'boolean') continue;
      const number = Number(value);
      if (Number.isFinite(number)) return number;
    }
    return null;
  };
  const input = read('input', 'input_per_million', 'input_cost', 'prompt', 'input_price_per_million');
  const output = read('output', 'output_per_million', 'output_cost', 'completion', 'output_price_per_million');
  if (input === null && output === null) return null;
  return { input: input ?? 0, output: output ?? 0 };
}

/**
 * Whether a completion probe may call this model.
 *
 * A completion probe is a real API call, billable if it lands on a paid model,
 * so a published price above zero is a hard skip -- probing it would spend
 * money to discover that it costs money.
 */
export function probeEligibility(row, { allowUnpriced = true, requireFreeLabel = false } = {}) {
  const price = listedPrice(row);
  const label = freeLabel(row);
  if (price !== null && (price.input > 0 || price.output > 0)) {
    return { eligible: false, note: `SKIPPED_PAID_MODEL input=${price.input} output=${price.output}` };
  }
  if (requireFreeLabel && !label) return { eligible: false, note: 'SKIPPED_NO_FREE_LABEL_IN_CATALOG' };
  if (price !== null) return { eligible: true, note: label ? `zero_price_in_catalog ${label}` : 'zero_price_in_catalog' };
  if (label) return { eligible: true, note: `free_label_in_catalog ${label}` };
  return allowUnpriced ? { eligible: true, note: 'unpriced_catalog' } : { eligible: false, note: 'SKIPPED_UNPRICED_MODEL' };
}

/** Union of row keys and one redacted sample, so a schema miss is visible. */
export function catalogShape(rows = []) {
  const keys = new Set();
  for (const row of rows.slice(0, 200)) {
    if (row && typeof row === 'object') for (const key of Object.keys(row)) keys.add(key);
  }
  return { keys: [...keys].sort(), sample: rows.length ? sanitizeForLog(rows[0]) : null };
}

// --- Display name -> live API id -------------------------------------------
//
// A vendor web catalog shows display names; the API speaks ids. Turning one
// into the other by hand is guessing, which is how two NVIDIA model ids that
// did not exist got admitted earlier. So the mapping is mechanical and
// conservative: normalize both sides, require exactly one live id to match, and
// report anything else as unresolved rather than picking a likely-looking one.

/** Lowercase, drop the vendor prefix, strip every non-alphanumeric character. */
export function normalizeModelKey(value) {
  const text = String(value ?? '').toLowerCase().trim();
  const withoutVendor = text.includes('/') ? text.slice(text.indexOf('/') + 1) : text;
  return withoutVendor.replace(/[^a-z0-9]/g, '');
}

/**
 * Resolve one display name against the live listing.
 * `matched` only when exactly one live id normalizes to the same key.
 */
export function resolveDisplayName(displayName, liveIds = []) {
  const key = normalizeModelKey(displayName);
  if (!key) return {displayName, status: 'unresolved', reason: 'EMPTY_NAME', candidates: []};
  const exact = liveIds.filter((id) => normalizeModelKey(id) === key);
  if (exact.length === 1) return {displayName, status: 'matched', id: exact[0], match: 'exact_normalized'};
  if (exact.length > 1) return {displayName, status: 'ambiguous', reason: 'MULTIPLE_EXACT_MATCHES', candidates: exact};
  // Deliberately no prefix or fuzzy fallback: "ising-calibration" must not
  // silently become "ising-calibration-1.5-31b". Near misses are reported so a
  // human can confirm the real id, never resolved automatically.
  // Containment, not just a shared prefix: "synthetic-video-detector" should
  // surface "ai-synthetic-video-detector" as something to confirm, even though
  // the live id carries an extra prefix.
  const near = liveIds.filter((id) => {
    const candidate = normalizeModelKey(id);
    return candidate.includes(key) || key.includes(candidate);
  });
  return {displayName, status: 'unresolved', reason: near.length ? 'NO_EXACT_MATCH' : 'NOT_IN_LIVE_LISTING', candidates: near.slice(0, 5)};
}

export function resolveDisplayNames(displayNames = [], liveIds = []) {
  return displayNames.map((name) => resolveDisplayName(name, liveIds));
}

// --- Modality ---------------------------------------------------------------
//
// The mesh needs text chat workers. Sending an embedding, speech or video model
// to /chat/completions would produce a meaningless 400 and tell us nothing, so
// each id is classified and only chat candidates are probed for that role. The
// rest keep their class so a future capability can use them deliberately.
const MODALITY_PATTERNS = [
  ['embedding', /(?:^|[-/])(?:embed|embedding|embedqa)|nv-embed|arctic-embed|nemoretriever/],
  ['rerank', /rerank/],
  ['reward', /reward/],
  ['safety', /guard|safety|topic-control|content-safety/],
  ['audio', /\b(?:tts|asr)\b|[-/](?:tts|asr)[-/]?|voice|speech|magpie|audio|noise/],
  ['video', /video|cosmos-transfer|streampetr|sparsedrive|bevformer/],
  ['vision_specialized', /vila|kosmos|deplot|nvclip|paligemma|fuyu|diffusiongemma|detector/],
];

/**
 * Classify a model id by modality. `text_chat` is the default because that is
 * what the mesh routes, and a vision-INSTRUCT model is a chat model that also
 * takes images -- not a vision-specialized endpoint.
 */
export function classifyModality(modelId) {
  const id = String(modelId ?? '').toLowerCase();
  if (!id) return 'unknown';
  if (/vision-instruct|vision-language|-vl-|multimodal-instruct/.test(id)) return 'text_chat';
  for (const [modality, pattern] of MODALITY_PATTERNS) {
    if (pattern.test(id)) return modality;
  }
  return 'text_chat';
}

export const CHAT_MODALITIES = Object.freeze(['text_chat']);
