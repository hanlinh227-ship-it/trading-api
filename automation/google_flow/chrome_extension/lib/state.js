const FINAL_STATES = new Set(['completed', 'failed', 'blocked', 'skipped']);
const INFLIGHT_STATES = new Set(['preflight', 'submitted', 'waiting', 'downloaded']);

function parseTime(value) {
  if (!value) return null;
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : t;
}

export function shouldProcess(command, history = { items: {}, order: [] }, nowMs = Date.now()) {
  const existing = history?.items?.[command.command_id];
  if (existing && FINAL_STATES.has(existing.state)) {
    return { process: false, reason: 'already-final' };
  }
  if (existing && INFLIGHT_STATES.has(existing.state)) {
    return { process: false, reason: 'already-inflight' };
  }
  const notBefore = parseTime(command.not_before);
  if (notBefore != null && nowMs < notBefore) return { process: false, reason: 'not-before' };
  const expiresAt = parseTime(command.expires_at);
  if (expiresAt != null && nowMs > expiresAt) return { process: false, reason: 'expired' };
  return { process: true, reason: 'runnable' };
}

export function markState(history = { items: {}, order: [] }, commandId, state, meta = {}, limit = 200, nowMs = Date.now()) {
  const items = { ...(history.items || {}) };
  const order = [...(history.order || [])].filter(id => id !== commandId);
  const sanitized = {
    state,
    scene: Number.isFinite(Number(meta.scene)) ? Number(meta.scene) : null,
    attempts: Number.isFinite(Number(meta.attempts)) ? Number(meta.attempts) : 0,
    error_code: typeof meta.error_code === 'string' ? meta.error_code : null,
    received_at: typeof meta.received_at === 'string' ? meta.received_at : null,
    updated_at: new Date(nowMs).toISOString(),
  };
  items[commandId] = sanitized;
  order.push(commandId);
  while (order.length > limit) {
    const evicted = order.shift();
    delete items[evicted];
  }
  return { items, order };
}

export function nextRunnableCommand(commands = [], history = { items: {}, order: [] }, nowMs = Date.now()) {
  const hasInflight = Object.values(history?.items || {}).some(item => INFLIGHT_STATES.has(item?.state));
  if (hasInflight) return null;
  return [...commands]
    .sort((a, b) => (Date.parse(a.created_at) || 0) - (Date.parse(b.created_at) || 0))
    .find(command => shouldProcess(command, history, nowMs).process) || null;
}

export function clearInflight(history = { items: {}, order: [] }, nowMs = Date.now()) {
  const items = { ...(history.items || {}) };
  for (const [commandId, item] of Object.entries(items)) {
    if (!INFLIGHT_STATES.has(item?.state)) continue;
    items[commandId] = {
      ...item,
      state: 'blocked',
      error_code: 'MANUAL_RESET',
      updated_at: new Date(nowMs).toISOString()
    };
  }
  return { items, order: [...(history.order || [])] };
}
