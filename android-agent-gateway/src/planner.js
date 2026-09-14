const ORDER = { A: 0, B: 1, C: 2, D: 3 }

export function deterministicPlan({ goal, allowedCapabilities = [], riskCeiling = 'A' }) {
  const lower = String(goal ?? '').toLowerCase()
  if (lower.includes('open settings') || lower.includes('mở cài đặt')) {
    return {
      action: { type: 'launch_app', packageName: 'com.android.settings' },
      expectedPostcondition: { type: 'foreground_package', packageName: 'com.android.settings' },
      requiredCapabilities: ['apps.open'].filter(x => allowedCapabilities.includes(x)),
      riskClass: ORDER[riskCeiling] >= ORDER.A ? 'A' : riskCeiling,
    }
  }
  return {
    action: { type: 'observe' },
    expectedPostcondition: { type: 'observation_returned' },
    requiredCapabilities: [],
    riskClass: 'A',
  }
}

export function clampPlan(plan, allowedCapabilities, riskCeiling) {
  if (!(riskCeiling in ORDER)) throw new Error('invalid risk ceiling')
  if (!(plan.riskClass in ORDER)) throw new Error('invalid planned risk')
  if (ORDER[plan.riskClass] > ORDER[riskCeiling]) throw new Error('planner risk escalation rejected')
  const allowed = new Set(allowedCapabilities)
  if (!(plan.requiredCapabilities ?? []).every(c => allowed.has(c))) {
    throw new Error('planner capability escalation rejected')
  }
  return {
    ...plan,
    requiredCapabilities: [...(plan.requiredCapabilities ?? [])],
  }
}
