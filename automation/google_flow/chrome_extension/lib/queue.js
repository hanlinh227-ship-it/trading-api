const ALLOWED_ACTIONS = new Set(['render']);
const ALLOWED_ASSET_MODES = new Set(['current', 'none', 'local_file', 'remote_url']);

export function isAllowedFlowUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return false;
    if (url.hostname === 'flow.google.com') return true;
    return url.hostname === 'labs.google' && (url.pathname === '/fx/tools/flow' || url.pathname.startsWith('/fx/tools/flow/'));
  } catch {
    return false;
  }
}

function parseTime(value, label, errors, commandId) {
  if (value == null) return null;
  const t = Date.parse(value);
  if (Number.isNaN(t)) {
    errors.push(`${commandId}: invalid ${label}`);
    return null;
  }
  return t;
}

export function normalizeCommand(raw = {}) {
  return {
    command_id: typeof raw.command_id === 'string' ? raw.command_id.trim() : '',
    created_at: raw.created_at ?? null,
    not_before: raw.not_before ?? null,
    expires_at: raw.expires_at ?? null,
    action: raw.action ?? '',
    project_url: raw.project_url ?? '',
    scene: Number(raw.scene),
    prompt: typeof raw.prompt === 'string' ? raw.prompt : '',
    duration_seconds: Number(raw.duration_seconds),
    aspect_ratio: raw.aspect_ratio ?? '16:9',
    start_image: raw.start_image ?? { mode: 'none' },
    end_image: raw.end_image ?? { mode: 'none' },
    output_filename: raw.output_filename ?? '',
    retry: raw.retry ?? { max_attempts: 1 },
  };
}

export function validateQueue(queue, nowMs = Date.now()) {
  const errors = [];
  const normalized = [];
  if (!queue || typeof queue !== 'object') {
    return { ok: false, errors: ['queue must be an object'], commands: [] };
  }
  if (queue.schema_version !== 1) errors.push('schema_version must equal 1');
  if (!Array.isArray(queue.commands)) {
    return { ok: false, errors: [...errors, 'commands must be an array'], commands: [] };
  }

  const seen = new Set();
  for (const raw of queue.commands) {
    const cmd = normalizeCommand(raw);
    const id = cmd.command_id || '<missing-id>';

    if (!cmd.command_id) errors.push(`${id}: command_id is required`);
    if (seen.has(cmd.command_id)) errors.push(`${id}: duplicate command_id`);
    seen.add(cmd.command_id);

    if (!ALLOWED_ACTIONS.has(cmd.action)) errors.push(`${id}: unsupported action`);
    if (!isAllowedFlowUrl(cmd.project_url)) errors.push(`${id}: project_url is not an allowed Flow URL`);
    if (!Number.isInteger(cmd.scene) || cmd.scene < 1) errors.push(`${id}: scene must be a positive integer`);
    if (!cmd.prompt.trim()) errors.push(`${id}: prompt is required`);
    if (!Number.isFinite(cmd.duration_seconds) || cmd.duration_seconds <= 0 || cmd.duration_seconds > 30) {
      errors.push(`${id}: duration_seconds out of range`);
    }
    if (!['16:9', '9:16', '1:1'].includes(cmd.aspect_ratio)) errors.push(`${id}: unsupported aspect_ratio`);

    const startMode = cmd.start_image?.mode;
    const endMode = cmd.end_image?.mode;
    if (!ALLOWED_ASSET_MODES.has(startMode)) errors.push(`${id}: invalid start_image mode`);
    if (!ALLOWED_ASSET_MODES.has(endMode)) errors.push(`${id}: invalid end_image mode`);

    const attempts = Number(cmd.retry?.max_attempts ?? 1);
    if (!Number.isInteger(attempts) || attempts < 1 || attempts > 1) {
      errors.push(`${id}: retry.max_attempts must equal 1`);
    }

    parseTime(cmd.created_at, 'created_at', errors, id);
    parseTime(cmd.not_before, 'not_before', errors, id);
    const expires = parseTime(cmd.expires_at, 'expires_at', errors, id);
    if (expires != null && nowMs > expires) errors.push(`${id}: command expired`);

    normalized.push(cmd);
  }

  return { ok: errors.length === 0, errors, commands: normalized };
}
