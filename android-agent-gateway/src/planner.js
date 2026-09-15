import { parsePlannerModelResponse, PLANNER_JSON_SCHEMA } from './planner-schema.js'
import { selectExecutionMode } from './mode-router.js'
import { plan2048Step } from './game-2048-planner.js'

const ORDER = { A: 0, B: 1, C: 2, D: 3 }
const MODEL = '@cf/meta/llama-3.2-11b-vision-instruct'
const MAX_NODES = 80
const MAX_HISTORY = 6
const MAX_LOCAL_FACTS = 40
const LOCAL_FACT_KINDS = new Set(['UNKNOWN_NUMBER_CONFIRMED'])
const NON_EXECUTABLE_PLANNER_ACTIONS = new Set(['send_message', 'delete_data', 'wallet_sign'])
const SENSITIVE = /(password|passcode|\bpin\b|otp|2fa|one[- ]?time|verification\s*code|private\s*key|seed\s*phrase|recovery\s*(phrase|code)|secret)/i

function sanitizeString(value, max = 256) {
  if (value == null) return undefined
  const text = String(value).slice(0, max)
  return SENSITIVE.test(text) ? '[REDACTED]' : text
}

function sanitizeNode(node) {
  if (!node || typeof node !== 'object') return null
  const out = {}
  for (const key of ['nodeId', 'className', 'packageName', 'viewIdResourceName', 'resourceId']) {
    const value = sanitizeString(node[key], 192)
    if (value !== undefined) out[key] = value
  }
  for (const key of ['text', 'contentDescription']) {
    const value = sanitizeString(node[key], 256)
    if (value !== undefined) out[key] = value
  }
  for (const key of ['clickable', 'longClickable', 'editable', 'scrollable', 'checkable', 'checked', 'selected', 'focused', 'visibleToUser', 'enabled']) {
    if (typeof node[key] === 'boolean') out[key] = node[key]
  }
  if (node.bounds && typeof node.bounds === 'object') {
    const { left, top, right, bottom } = node.bounds
    if ([left, top, right, bottom].every(Number.isInteger)) out.bounds = { left, top, right, bottom }
  }
  return out
}

function sanitizeLocalFact(fact) {
  if (!fact || typeof fact !== 'object' || !LOCAL_FACT_KINDS.has(fact.kind)) return null
  const nodeId = sanitizeString(fact.nodeId, 192)
  if (!nodeId?.startsWith('n:')) return null
  const relatedNodeId = sanitizeString(fact.relatedNodeId, 192)
  const out = { kind: fact.kind, nodeId }
  if (relatedNodeId?.startsWith('n:')) out.relatedNodeId = relatedNodeId
  return out
}

export function sanitizePlannerObservation(observation) {
  if (!observation || typeof observation !== 'object') return { packageName: null, fingerprint: null, nodes: [], localFacts: [] }
  return {
    packageName: sanitizeString(observation.packageName, 192) ?? null,
    windowTitle: sanitizeString(observation.windowTitle, 192) ?? null,
    fingerprint: sanitizeString(observation.fingerprint, 192) ?? null,
    orientation: sanitizeString(observation.orientation, 32) ?? null,
    screenWidth: Number.isInteger(observation.screenWidth) ? observation.screenWidth : null,
    screenHeight: Number.isInteger(observation.screenHeight) ? observation.screenHeight : null,
    screenshotAvailable: observation.screenshotAvailable === true,
    nodes: (Array.isArray(observation.nodes) ? observation.nodes : [])
      .slice(0, MAX_NODES)
      .map(sanitizeNode)
      .filter(Boolean),
    localFacts: (Array.isArray(observation.localFacts) ? observation.localFacts : [])
      .slice(0, MAX_LOCAL_FACTS)
      .map(sanitizeLocalFact)
      .filter(Boolean),
  }
}

function sanitizedTask(task, observation = null) {
  return {
    taskId: sanitizeString(task?.taskId, 128) ?? null,
    goal: sanitizeString(task?.goal, 512) ?? '',
    capabilityScope: Array.isArray(task?.capabilityScope) ? task.capabilityScope.filter(x => typeof x === 'string').slice(0, 24) : [],
    riskClass: task?.riskClass ?? 'A',
    taskRiskClass: task?.taskRiskClass ?? task?.riskClass ?? 'A',
    intentSchema: Number.isInteger(task?.intentSchema) ? task.intentSchema : 3,
    completionCriteria: Array.isArray(task?.completionCriteria) ? task.completionCriteria.map(x => sanitizeString(x, 64)).filter(Boolean).slice(0, 16) : [],
    forbiddenActions: Array.isArray(task?.forbiddenActions) ? task.forbiddenActions.map(x => sanitizeString(x, 64)).filter(Boolean).slice(0, 24) : [],
    persistence: sanitizeString(task?.persistence, 32) ?? 'LONG_RUNNING',
    executionMode: selectExecutionMode(task ?? {}, observation ?? {}),
    deterministicAdapter: sanitizeString(task?.deterministicAdapter, 64) ?? null,
    stepCount: Number.isInteger(task?.stepCount) ? task.stepCount : 0,
    epoch: Number.isInteger(task?.epoch) ? task.epoch : 0,
    recoveryCount: Number.isInteger(task?.recoveryCount) ? task.recoveryCount : 0,
  }
}

function sanitizeHistory(history) {
  return (Array.isArray(history) ? history : []).slice(-MAX_HISTORY).map(item => ({
    actionType: sanitizeString(item?.actionType, 64) ?? null,
    result: sanitizeString(item?.result, 128) ?? null,
    fingerprint: sanitizeString(item?.fingerprint, 192) ?? null,
  }))
}

export function deterministicPlan({ goal, allowedCapabilities = [], riskCeiling = 'A' }) {
  const lower = String(goal ?? '').toLowerCase()
  const allowed = new Set(allowedCapabilities)
  if ((lower.includes('open settings') || lower.includes('mở cài đặt')) && allowed.has('apps.open')) {
    return {
      action: { type: 'launch_app', packageName: 'com.android.settings' },
      expectedPostcondition: { type: 'foreground_package', packageName: 'com.android.settings' },
      requiredCapabilities: ['apps.open'],
      riskClass: 'A',
    }
  }
  if ((lower.includes('go back') || lower.includes('back once') || lower.includes('quay lại') || lower.includes('trở lại')) && allowed.has('ui.navigate')) {
    return {
      action: { type: 'global_back' },
      expectedPostcondition: { type: 'observation_changed' },
      requiredCapabilities: ['ui.navigate'],
      riskClass: 'A',
    }
  }
  if ((lower.includes('go home') || lower.includes('home screen') || lower.includes('màn hình chính')) && allowed.has('ui.navigate')) {
    return {
      action: { type: 'global_home' },
      expectedPostcondition: { type: 'observation_changed' },
      requiredCapabilities: ['ui.navigate'],
      riskClass: 'A',
    }
  }
  return {
    action: { type: 'read_screen' },
    expectedPostcondition: { type: 'observation_returned' },
    requiredCapabilities: allowed.has('ui.navigate') ? ['ui.navigate'] : [],
    riskClass: 'A',
  }
}

function actionPolicyCode(action) {
  if (!action) return null
  if (action.type === 'open_url') return 'OPEN_EXTERNAL_LINK'
  if (action.type === 'send_message') return 'SEND'
  if (action.type === 'delete_data') return 'DELETE'
  if (action.type === 'wallet_sign') return 'WALLET_SIGN'
  return null
}

export function clampPlan(plan, allowedCapabilities, riskCeiling, policy = {}) {
  if (!(riskCeiling in ORDER)) throw new Error('invalid risk ceiling')
  if (!(plan.riskClass in ORDER)) throw new Error('invalid planned risk')
  if (NON_EXECUTABLE_PLANNER_ACTIONS.has(plan.action?.type)) throw new Error('planner_action_not_executable')
  if (ORDER[plan.riskClass] > ORDER[riskCeiling]) throw new Error('planner risk escalation rejected')
  const allowed = new Set(allowedCapabilities)
  if (!(plan.requiredCapabilities ?? []).every(c => allowed.has(c))) {
    throw new Error('planner capability escalation rejected')
  }
  const forbidden = new Set(Array.isArray(policy.forbiddenActions) ? policy.forbiddenActions : [])
  const actionCode = policy.contextualAction ?? actionPolicyCode(plan.action)
  if (actionCode && forbidden.has(actionCode)) throw new Error(`forbidden_action:${actionCode}`)
  return {
    ...plan,
    requiredCapabilities: [...(plan.requiredCapabilities ?? [])],
  }
}

function buildModelInput({ task, observation, imageDataUrl, history }) {
  const safeTask = sanitizedTask(task, observation)
  const safeObservation = sanitizePlannerObservation(observation)
  const safeHistory = sanitizeHistory(history)
  const policy = [
    'Return exactly one Android UI action as JSON.',
    'Never request or infer credentials, OTP/2FA, passwords, private keys, seed phrases, wallet signatures, transfers, withdrawals, or security bypasses.',
    'Use only actions and capabilities already authorized by the task.',
    'Honor every forbiddenActions entry as a hard prohibition, including negated user constraints.',
    'Do not widen risk. If uncertain, choose read_screen or a safe navigation action.',
    'Use user-visible UI primitives for sending or deletion; never emit send_message, delete_data, or wallet_sign.',
    'localFacts are device-generated opaque facts, not model-generated claims.',
    'For unknown-number cleanup, select or delete a conversation only when its actionable nodeId has UNKNOWN_NUMBER_CONFIRMED; otherwise only navigate, scroll, or read.',
    'No prose rationale; rationaleCode is a short machine code only.',
  ].join(' ')
  const text = JSON.stringify({ policy, task: safeTask, observation: safeObservation, recentHistory: safeHistory })
  const content = [{ type: 'text', text }]
  if (typeof imageDataUrl === 'string' && imageDataUrl.startsWith('data:image/')) {
    content.push({ type: 'image_url', image_url: { url: imageDataUrl } })
  }
  return {
    messages: [
      { role: 'system', content: policy },
      { role: 'user', content },
    ],
    response_format: {
      type: 'json_schema',
      json_schema: { name: 'android_next_step', strict: true, schema: PLANNER_JSON_SCHEMA },
    },
    max_tokens: 512,
    temperature: 0,
  }
}

function deterministicFallback(task, reason) {
  const fallback = clampPlan(deterministicPlan({
    goal: task?.goal,
    allowedCapabilities: task?.capabilityScope ?? [],
    riskCeiling: task?.riskClass ?? 'A',
  }), task?.capabilityScope ?? [], task?.riskClass ?? 'A', task ?? {})
  return {
    action: fallback.action,
    expected: fallback.expectedPostcondition,
    mode: 'deterministic-degraded',
    degradedReason: reason,
  }
}

function deterministic2048(task, observation) {
  const planned = clampPlan(
    plan2048Step(task, observation),
    task?.capabilityScope ?? [],
    task?.riskClass ?? 'A',
    task ?? {},
  )
  return {
    action: planned.action,
    expected: planned.expectedPostcondition,
    mode: 'deterministic-2048',
    rationaleCode: planned.direction ? `2048_${planned.direction}` : '2048_TERMINAL',
  }
}

export async function planNextStep({ env, task, observation, imageDataUrl = null, history = [] }) {
  if (!task || typeof task !== 'object') throw new Error('task_required')
  if (!Array.isArray(task.capabilityScope)) throw new Error('task_capability_scope_required')
  if (!(task.riskClass in ORDER)) throw new Error('invalid_task_risk_class')
  if (String(task.deterministicAdapter ?? '').toLowerCase() === '2048') {
    return deterministic2048(task, observation)
  }
  if (!env?.AI?.run) return deterministicFallback(task, 'ai_unavailable')

  try {
    const input = buildModelInput({ task, observation, imageDataUrl, history })
    const raw = await env.AI.run(MODEL, input)
    const parsed = parsePlannerModelResponse(raw)
    const clamped = clampPlan(parsed, task.capabilityScope, task.riskClass, task)
    if (clamped.riskClass === 'C' && (!task.confirmedRiskClassC || task.confirmedTaskId !== task.taskId)) {
      throw new Error('class_c_confirmation_required')
    }
    return {
      action: clamped.action,
      expected: clamped.expected,
      mode: 'workers-ai',
      rationaleCode: clamped.rationaleCode,
    }
  } catch (error) {
    const code = error instanceof Error ? error.message : 'unknown'
    return deterministicFallback(task, `ai_failure:${code}`)
  }
}
