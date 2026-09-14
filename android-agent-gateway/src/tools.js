import { interpretTaskIntent } from './task-intent.js'

export function classifyGoal(goal) {
  return interpretTaskIntent(goal).riskClass
}

export function validateRunGoal(input) {
  if (!input || typeof input !== 'object') throw new Error('input required')
  const allowedKeys = new Set(['deviceId', 'goal', 'capabilityScope', 'riskCeiling', 'confirmedRiskClassC'])
  for (const key of Object.keys(input)) {
    if (!allowedKeys.has(key)) throw new Error(`unsupported field: ${key}`)
  }
  if (typeof input.deviceId !== 'string' || !input.deviceId.trim()) throw new Error('deviceId required')
  if (typeof input.goal !== 'string' || !input.goal.trim()) throw new Error('goal required')
  if (input.confirmedRiskClassC != null && typeof input.confirmedRiskClassC !== 'boolean') {
    throw new Error('confirmedRiskClassC must be boolean')
  }
  return {
    deviceId: input.deviceId.trim(),
    goal: input.goal.trim(),
    capabilityScope: Array.isArray(input.capabilityScope) ? input.capabilityScope : ['apps.open', 'ui.navigate'],
    riskCeiling: input.riskCeiling ?? 'C',
    confirmedRiskClassC: input.confirmedRiskClassC === true,
  }
}

export const TOOL_CONTRACT = Object.freeze({
  android_device_status: { write: false },
  android_run_goal: { write: true, rawShell: false },
  android_get_task: { write: false },
  android_confirm_action: { write: true },
  android_cancel_task: { write: true },
})
