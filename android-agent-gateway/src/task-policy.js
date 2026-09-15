import { typedActionMetadata } from './action-schema.js'

const RISK_ORDER = Object.freeze({ A: 0, B: 1, C: 2, D: 3 })
const EPOCH_ACTION_LIMIT = 50
const MAX_EPOCHS = 20
const MAX_TOTAL_ACTIONS = EPOCH_ACTION_LIMIT * MAX_EPOCHS
const MAX_RECOVERIES = 5

const RISK_D_TERMS = [
  'otp', 'one-time password', 'one time password', '2fa', 'mfa', 'password', 'passcode',
  'enter pin', 'confirm pin', 'verification code', 'security code', 'seed phrase', 'recovery phrase',
  'private key', 'wallet sign', 'sign transaction', 'transfer money', 'withdraw',
  'mật khẩu', 'mã otp', 'mã pin', 'mã xác minh', 'cụm từ khôi phục', 'khóa riêng', 'chuyển tiền', 'rút tiền',
  'disable security', 'tắt bảo mật',
]
const RISK_C_TERMS = [
  'delete', 'remove', 'erase', 'trash', 'uninstall', 'purchase', 'buy ', 'pay ', 'checkout',
  'send', 'publish', 'post', 'share publicly',
  'xóa', 'xoá', 'gỡ', 'thùng rác', 'mua ', 'thanh toán', 'gửi', 'đăng', 'công khai',
]
const RISK_B_TERMS = [
  'save', 'apply', 'edit', 'rename', 'toggle', 'switch', 'enable', 'disable', 'turn on', 'turn off',
  'lưu', 'áp dụng', 'chỉnh', 'đổi tên', 'bật', 'tắt',
]

function assertRisk(value) {
  if (!(value in RISK_ORDER)) throw new Error('invalid_risk_class')
  return value
}

function maxRisk(...values) {
  return values.reduce((highest, value) => (
    RISK_ORDER[assertRisk(value)] > RISK_ORDER[highest] ? value : highest
  ), 'A')
}

function normalizedText(value) {
  return typeof value === 'string' ? value.toLowerCase().replace(/\s+/g, ' ').trim() : ''
}

function textRisk(text) {
  const value = normalizedText(text)
  if (!value) return 'A'
  if (RISK_D_TERMS.some(term => value.includes(term))) return 'D'
  if (RISK_C_TERMS.some(term => value.includes(term))) return 'C'
  if (RISK_B_TERMS.some(term => value.includes(term))) return 'B'
  return 'A'
}

function nodeArea(node) {
  const b = node?.bounds
  if (!b) return Number.POSITIVE_INFINITY
  const width = Math.max(0, Number(b.right) - Number(b.left))
  const height = Math.max(0, Number(b.bottom) - Number(b.top))
  return width * height
}

function pointInside(node, x, y) {
  const b = node?.bounds
  if (!b) return false
  return x >= Number(b.left) && x <= Number(b.right) && y >= Number(b.top) && y <= Number(b.bottom)
}

function targetNode(action, observation) {
  const nodes = Array.isArray(observation?.nodes) ? observation.nodes : []
  if (['click_node', 'long_click_node', 'set_text', 'replace_text', 'clipboard_paste'].includes(action.type)) {
    const selector = normalizedText(action.selector)
    if (!selector) return null
    if (selector.startsWith('n:')) return nodes.find(node => node?.nodeId === action.selector) ?? null
    return nodes.find(node => [node?.resourceId, node?.text, node?.contentDescription]
      .some(value => normalizedText(value).includes(selector))) ?? null
  }
  if (['tap_point', 'long_press_point', 'double_tap_point'].includes(action.type)) {
    return nodes
      .filter(node => node?.visibleToUser !== false && pointInside(node, action.x, action.y))
      .sort((a, b) => nodeArea(a) - nodeArea(b))[0] ?? null
  }
  return null
}

function contextualRisk(action, observation) {
  const node = targetNode(action, observation)
  if (!node) return 'A'
  const context = [
    observation?.windowTitle,
    node.resourceId,
    node.text,
    node.contentDescription,
    node.className,
  ].filter(Boolean).join(' ')
  let risk = textRisk(context)
  const className = normalizedText(node.className)
  if (node.checkable === true || /switch|checkbox|radiobutton|toggle|seekbar/.test(className)) {
    risk = maxRisk(risk, 'B')
  }
  return risk
}

function contextualActionCode(action, observation) {
  if (action?.type === 'wallet_sign') return 'WALLET_SIGN'
  if (action?.type === 'send_message') return 'SEND'
  if (action?.type === 'delete_data') return 'DELETE'
  if (action?.type === 'open_url') return 'OPEN_EXTERNAL_LINK'
  const node = targetNode(action, observation)
  const context = normalizedText([
    observation?.windowTitle,
    node?.resourceId,
    node?.text,
    node?.contentDescription,
  ].filter(Boolean).join(' '))
  if (!context) return null
  if (/\b(?:ad|ads|advertisement)\b|quảng cáo/u.test(context)) return 'OPEN_AD'
  if (/\b(?:buy|purchase|checkout|pay)\b|mua|thanh toán/u.test(context)) return 'PURCHASE'
  if (/\b(?:delete|remove|erase|trash)\b|xóa|xoá|thùng rác/u.test(context)) return 'DELETE'
  if (/\b(?:send|submit|publish|post|share)\b|gửi|đăng/u.test(context)) return 'SEND'
  if (/\b(?:password|passcode|otp|2fa|private key|seed phrase|recovery phrase)\b|mật khẩu|mã otp|khóa riêng|khoá riêng/u.test(context)) return 'CREDENTIAL_ACCESS'
  return null
}

export function createTaskState(input) {
  if (!input?.taskId || typeof input.taskId !== 'string') throw new Error('task_id_required')
  if (!input?.goal || typeof input.goal !== 'string') throw new Error('task_goal_required')
  if (!Array.isArray(input.capabilityScope)) throw new Error('invalid_capability_scope')
  const riskClass = assertRisk(input.riskClass ?? 'A')
  const taskRiskClass = assertRisk(input.taskRiskClass ?? riskClass)
  if (RISK_ORDER[taskRiskClass] > RISK_ORDER[riskClass]) throw new Error('task_risk_exceeds_ceiling')
  return {
    taskId: input.taskId,
    goal: input.goal,
    intentSchema: Number.isInteger(input.intentSchema) ? input.intentSchema : 3,
    completionCriteria: Array.isArray(input.completionCriteria) ? [...new Set(input.completionCriteria.map(String))].slice(0, 16) : [],
    forbiddenActions: Array.isArray(input.forbiddenActions) ? [...new Set(input.forbiddenActions.map(String))].slice(0, 24) : [],
    executionMode: input.executionMode ?? 'AUTO',
    deterministicAdapter: input.deterministicAdapter ?? null,
    persistence: input.persistence ?? 'LONG_RUNNING',
    userConstraints: Array.isArray(input.userConstraints) ? input.userConstraints.map(String).slice(0, 16) : [],
    capabilityScope: [...new Set(input.capabilityScope)].sort(),
    riskClass,
    taskRiskClass,
    confirmedRiskClassC: Boolean(input.confirmedRiskClassC),
    confirmedTaskId: input.confirmedTaskId ?? null,
    status: input.status ?? 'QUEUED',
    stepCount: Number.isInteger(input.stepCount) ? input.stepCount : 0,
    epoch: Number.isInteger(input.epoch) ? input.epoch : 0,
    epochStepCount: Number.isInteger(input.epochStepCount) ? input.epochStepCount : 0,
    checkpointCount: Number.isInteger(input.checkpointCount) ? input.checkpointCount : 0,
    progressMarker: input.progressMarker ?? null,
    checkpointProgressMarker: input.checkpointProgressMarker ?? null,
    epochStartProgressMarker: input.epochStartProgressMarker ?? null,
    epochProgressed: Boolean(input.epochProgressed),
    stalledAtCheckpoint: Boolean(input.stalledAtCheckpoint),
    recoveryCount: Number.isInteger(input.recoveryCount) ? input.recoveryCount : 0,
    lastFingerprint: input.lastFingerprint ?? null,
    failureCode: input.failureCode ?? null,
    createdAt: input.createdAt ?? new Date().toISOString(),
    updatedAt: input.updatedAt ?? new Date().toISOString(),
  }
}

export function confirmTaskState(task, taskId) {
  if (!task || task.taskId !== taskId) throw new Error('task_confirmation_mismatch')
  if (task.taskRiskClass !== 'C' && task.riskClass !== 'C') throw new Error('task_confirmation_not_required')
  return { ...task, confirmedRiskClassC: true, confirmedTaskId: task.taskId, updatedAt: new Date().toISOString() }
}

export function cancelTaskState(task) {
  if (!task) throw new Error('task_required')
  if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(task.status)) return task
  return {
    ...task,
    status: 'CANCELLED',
    failureCode: 'USER_CANCELLED',
    updatedAt: new Date().toISOString(),
  }
}

export function clampTaskStep({ task, action, observation = null }) {
  if (!task) throw new Error('task_required')
  const { action: normalized, riskClass: actionRisk, capability } = typedActionMetadata(action)
  const ceiling = assertRisk(task.riskClass)
  const taskRisk = assertRisk(task.taskRiskClass ?? task.riskClass)
  const contextRisk = contextualRisk(normalized, observation)
  const effectiveRisk = maxRisk(taskRisk, actionRisk, contextRisk)
  const contextualAction = contextualActionCode(normalized, observation)

  if (effectiveRisk === 'D') throw new Error('class_d_denied')
  if (contextualAction && Array.isArray(task.forbiddenActions) && task.forbiddenActions.includes(contextualAction)) {
    throw new Error(`forbidden_action:${contextualAction}`)
  }
  if (!Array.isArray(task.capabilityScope) || !task.capabilityScope.includes(capability)) {
    throw new Error('capability_escalation_denied')
  }
  if (RISK_ORDER[effectiveRisk] > RISK_ORDER[ceiling]) throw new Error('risk_escalation_denied')
  if (effectiveRisk === 'C') {
    if (!task.confirmedRiskClassC || task.confirmedTaskId !== task.taskId) {
      throw new Error('class_c_confirmation_required')
    }
  }
  return { action: normalized, riskClass: effectiveRisk, capability, contextRisk, contextualAction }
}

export function recordTaskProgress(task, event) {
  const next = { ...task, updatedAt: new Date().toISOString() }
  if (event?.kind === 'step') {
    if (next.stalledAtCheckpoint) throw new Error('no_progress_detected')
    if ((next.stepCount ?? 0) >= MAX_TOTAL_ACTIONS || (next.epoch ?? 0) >= MAX_EPOCHS) {
      throw new Error('max_epochs_exceeded')
    }

    const marker = event.progressMarker !== undefined ? event.progressMarker : event.fingerprint
    let epochStart = next.epochStartProgressMarker
    let epochProgressed = Boolean(next.epochProgressed)
    if ((next.epochStepCount ?? 0) === 0) {
      epochStart = marker ?? null
      epochProgressed = false
    } else if (marker != null && epochStart != null && marker !== epochStart) {
      epochProgressed = true
    }

    next.stepCount = (next.stepCount ?? 0) + 1
    next.epochStepCount = (next.epochStepCount ?? 0) + 1
    next.progressMarker = marker ?? next.progressMarker ?? null
    next.epochStartProgressMarker = epochStart
    next.epochProgressed = epochProgressed

    if (next.epochStepCount >= EPOCH_ACTION_LIMIT) {
      next.epoch = (next.epoch ?? 0) + 1
      next.checkpointCount = (next.checkpointCount ?? 0) + 1
      next.checkpointProgressMarker = next.progressMarker
      next.stalledAtCheckpoint = next.persistence === 'UNTIL_TERMINAL' && !epochProgressed
      next.epochStepCount = 0
      next.epochStartProgressMarker = null
      next.epochProgressed = false
    }
  } else if (event?.kind === 'recovery') {
    if ((next.recoveryCount ?? 0) >= MAX_RECOVERIES) throw new Error('max_recoveries_exceeded')
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
    intentSchema: task.intentSchema ?? 3,
    completionCriteria: task.completionCriteria ?? [],
    forbiddenActions: task.forbiddenActions ?? [],
    executionMode: task.executionMode ?? 'AUTO',
    deterministicAdapter: task.deterministicAdapter ?? null,
    persistence: task.persistence ?? 'LONG_RUNNING',
    capabilityScope: task.capabilityScope,
    riskClass: task.riskClass,
    taskRiskClass: task.taskRiskClass ?? task.riskClass,
    confirmedRiskClassC: Boolean(task.confirmedRiskClassC),
    status: task.status,
    stepCount: task.stepCount,
    epoch: task.epoch ?? 0,
    epochStepCount: task.epochStepCount ?? 0,
    checkpointCount: task.checkpointCount ?? 0,
    recoveryCount: task.recoveryCount,
    lastFingerprint: task.lastFingerprint ?? null,
    failureCode: typeof task.failureCode === 'string' ? task.failureCode.slice(0, 96) : null,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt,
  }
}

export const TASK_LIMITS = Object.freeze({ EPOCH_ACTION_LIMIT, MAX_EPOCHS, MAX_TOTAL_ACTIONS, MAX_RECOVERIES })
