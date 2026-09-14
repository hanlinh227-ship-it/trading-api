import { typedActionMetadata } from './action-schema.js'

const RISK_ORDER = Object.freeze({ A: 0, B: 1, C: 2, D: 3 })

function assertRisk(value) {
  if (!(value in RISK_ORDER)) throw new Error('invalid_risk_class')
  return value
}

export function createTaskState(input) {
  if (!input?.taskId || typeof input.taskId !== 'string') throw new Error('task_id_required')
  if (!input?.goal || typeof input.goal !== 'string') throw new Error('task_goal_required')
  if (!Array.isArray(input.capabilityScope)) throw new Error('invalid_capability_scope')
  const riskClass = assertRisk(input.riskClass ?? 'A')
  return {
    taskId: input.taskId,
    goal: input.goal,
    capabilityScope: [...new Set(input.capabilityScope)].sort(),
    riskClass,
    confirmedRiskClassC: Boolean(input.confirmedRiskClassC),
    confirmedTaskId: input.confirmedTaskId ?? null,
    status: input.status ?? 'QUEUED',
    stepCount: Number.isInteger(input.stepCount) ? input.stepCount : 0,
    recoveryCount: Number.isInteger(input.recoveryCount) ? input.recoveryCount : 0,
    lastFingerprint: input.lastFingerprint ?? null,
    createdAt: input.createdAt ?? new Date().toISOString(),
    updatedAt: input.updatedAt ?? new Date().toISOString(),
  }
}

export function clampTaskStep({ task, action }) {
  if (!task) throw new Error('task_required')
  const { action: normalized, riskClass: actionRisk, capability } = typedActionMetadata(action)
  const ceiling = assertRisk(task.riskClass)
  if (actionRisk === 'D') throw new Error('class_d_denied')
  if (!Array.isArray(task.capabilityScope) || !task.capabilityScope.includes(capability)) {
    throw new Error('capability_escalation_denied')
  }
  if (RISK_ORDER[actionRisk] > RISK_ORDER[ceiling]) throw new Error('risk_escalation_denied')
  if (actionRisk === 'C') {
    if (!task.confirmedRiskClassC || task.confirmedTaskId !== task.taskId) {
      throw new Error('class_c_confirmation_required')
    }
  }
  return { action: normalized, riskClass: actionRisk, capability }
}

export function recordTaskProgress(task, event) {
  const next = { ...task, updatedAt: new Date().toISOString() }
  if (event?.kind === 'step') {
    if ((next.stepCount ?? 0) >= 40) throw new Error('max_steps_exceeded')
    next.stepCount = (next.stepCount ?? 0) + 1
  } else if (event?.kind === 'recovery') {
    if ((next.recoveryCount ?? 0) >= 5) throw new Error('max_recoveries_exceeded')
    next.recoveryCount = (next.recoveryCount ?? 0) + 1
  } else {
    throw new Error('invalid_task_progress_event')
  }
  if (event.fingerprint !== undefined) next.lastFingerprint = event.fingerprint
  if (event.status) next.status = event.status
  return next
}

export function publicTaskState(task) {
  if (!task) return null
  return {
    taskId: task.taskId,
    goal: task.goal,
    capabilityScope: task.capabilityScope,
    riskClass: task.riskClass,
    confirmedRiskClassC: Boolean(task.confirmedRiskClassC),
    status: task.status,
    stepCount: task.stepCount,
    recoveryCount: task.recoveryCount,
    lastFingerprint: task.lastFingerprint ?? null,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt,
  }
}
