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
