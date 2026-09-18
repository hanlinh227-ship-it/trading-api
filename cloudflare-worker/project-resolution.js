// Project resolution for the Front Door Closure plan (Task 1).
//
// This module is intentionally small, deterministic, fail-closed, and
// non-authoritative. It performs NO routing, reasoning, scheduling, or
// trading. It never guesses across projects and never persists or logs
// secret material, transcript content, or connector tokens.
//
// Interface:
//   resolveProjectId(request, clientConfig, storedDefault) -> string | null
//
// Precedence (highest first):
//   1. explicit project_id supplied by the authenticated request, when valid
//   2. explicitly approved client default
//   3. explicitly stored approved default
//
// Any malformed, empty, non-string, ambiguous, or unapproved input fails
// closed by returning null rather than guessing.

const MAX_PROJECT_ID_LENGTH = 128;

// Conservative, deterministic project id shape. No guessing, no coercion.
const PROJECT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;

/**
 * Validate a candidate project id.
 * Returns the normalized id string, or null when invalid.
 * Never coerces non-strings, never trims into validity, never guesses.
 */
export function normalizeProjectId(value) {
  if (typeof value !== "string") {
    return null;
  }
  if (value.length === 0 || value.length > MAX_PROJECT_ID_LENGTH) {
    return null;
  }
  if (value !== value.trim()) {
    return null;
  }
  if (!PROJECT_ID_PATTERN.test(value)) {
    return null;
  }
  return value;
}

/**
 * Extract the explicit project id from an authenticated request.
 *
 * Accepts a plain object with a `project_id` field. If the request carries
 * multiple conflicting project identifiers, this fails closed (returns a
 * sentinel indicating ambiguity) rather than picking one.
 *
 * Returns one of:
 *   { status: "absent" }
 *   { status: "valid", value: string }
 *   { status: "invalid" }
 *   { status: "ambiguous" }
 */
function readExplicitProjectId(request) {
  if (request === null || typeof request !== "object") {
    return { status: "absent" };
  }

  const candidates = [];
  if (Object.prototype.hasOwnProperty.call(request, "project_id")) {
    candidates.push(request.project_id);
  }
  if (Object.prototype.hasOwnProperty.call(request, "projectId")) {
    candidates.push(request.projectId);
  }

  if (candidates.length === 0) {
    return { status: "absent" };
  }

  const normalized = [];
  for (const candidate of candidates) {
    const id = normalizeProjectId(candidate);
    if (id === null) {
      return { status: "invalid" };
    }
    normalized.push(id);
  }

  const unique = new Set(normalized);
  if (unique.size > 1) {
    return { status: "ambiguous" };
  }

  return { status: "valid", value: normalized[0] };
}

/**
 * Read an explicitly approved default from a config-like object.
 *
 * The default is only honored when it is explicitly marked approved
 * (`approved === true`). Anything else fails closed to null.
 */
function readApprovedDefault(container) {
  if (container === null || typeof container !== "object") {
    return null;
  }
  if (container.approved !== true) {
    return null;
  }
  return normalizeProjectId(container.project_id);
}

/**
 * Resolve the effective project id.
 *
 * @param {unknown} request        authenticated request (may carry project_id)
 * @param {unknown} clientConfig   client config (may carry approved default)
 * @param {unknown} storedDefault  stored default (may carry approved default)
 * @returns {string|null}
 */
export function resolveProjectId(request, clientConfig, storedDefault) {
  const explicit = readExplicitProjectId(request);

  if (explicit.status === "ambiguous" || explicit.status === "invalid") {
    // Conflicting or malformed explicit identifiers fail closed.
    return null;
  }

  if (explicit.status === "valid") {
    return explicit.value;
  }

  // No explicit id: fall back to explicitly approved defaults only.
  const clientDefault = readApprovedDefault(clientConfig);
  if (clientDefault !== null) {
    return clientDefault;
  }

  const stored = readApprovedDefault(storedDefault);
  if (stored !== null) {
    return stored;
  }

  // Never guess across projects.
  return null;
}

export { MAX_PROJECT_ID_LENGTH };
