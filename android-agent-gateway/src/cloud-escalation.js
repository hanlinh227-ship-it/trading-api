import { planNextStep } from './planner.js'

const METRIC_KEYS = new Set([
  'localDecisionLatencyMs',
  'actionDispatchLatencyMs',
  'actionToEventLatencyMs',
  'verifierLatencyMs',
  'localReasoningCount',
  'cloudReasoningCount',
  'screenMapHitRate',
  'verifiedSkillHitRate',
  'recoveryRate',
  'screenshotRate',
  'cancellationLatencyMs',
])

export async function planMicroActions(context, maxActions = 8) {
  const limit = Math.max(1, Math.min(8, Number(maxActions) || 1))
  const planned = await planNextStep(context)
  if (!planned?.action || planned?.expected?.type === 'task_complete') {
    return { actions: [], expected: planned?.expected ?? { type: 'task_complete' }, mode: planned?.mode ?? 'unknown' }
  }
  return {
    actions: [planned.action].slice(0, limit),
    expected: planned.expected ?? { type: 'observation_returned' },
    mode: planned.mode ?? 'unknown',
  }
}

export function sanitizeMetrics(input = {}) {
  const out = {}
  for (const [key, value] of Object.entries(input ?? {})) {
    if (!METRIC_KEYS.has(key)) continue
    if (typeof value !== 'number' || !Number.isFinite(value)) continue
    out[key] = value
  }
  return out
}

export function sanitizeCheckpoint(input = {}) {
  return {
    stepCount: Number.isInteger(input.stepCount) && input.stepCount >= 0 ? input.stepCount : 0,
    epoch: Number.isInteger(input.epoch) && input.epoch >= 0 ? input.epoch : 0,
    checkpointCount: Number.isInteger(input.checkpointCount) && input.checkpointCount >= 0 ? input.checkpointCount : 0,
    screenSignature: typeof input.screenSignature === 'string' ? input.screenSignature.slice(0, 192) : null,
    selectedSkillId: typeof input.selectedSkillId === 'string' ? input.selectedSkillId.slice(0, 96) : null,
    metrics: sanitizeMetrics(input.metrics),
    recordedAt: new Date().toISOString(),
  }
}
