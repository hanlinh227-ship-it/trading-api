const MUTATING_HIGH_RISK = new Set(['send_message', 'delete_data', 'wallet_sign'])

function capabilityFor(action) {
  switch (action?.type) {
    case 'launch_app':
    case 'open_url': return 'apps.open'
    case 'set_text':
    case 'clear_text':
    case 'replace_text':
    case 'clipboard_set':
    case 'clipboard_paste': return 'ui.write'
    default: return 'ui.navigate'
  }
}

function safeAnchor(anchor) {
  if (!anchor || typeof anchor !== 'object') return null
  const out = {}
  for (const key of ['text', 'resourceId', 'contentDescription', 'className']) {
    if (typeof anchor[key] === 'string' && anchor[key].trim()) out[key] = anchor[key].trim().slice(0, 192)
  }
  return Object.keys(out).length ? out : null
}

export function candidateFromTrajectory({ task, packageName, history }) {
  if (!task || !packageName || !Array.isArray(history) || history.length === 0) return null
  if (task.taskRiskClass === 'C' || task.taskRiskClass === 'D' || task.riskClass === 'D') return null

  const verified = history.filter(item => item?.verified === true && item.action && !MUTATING_HIGH_RISK.has(item.action.type))
  if (verified.length === 0) return null
  if (verified.some(item => MUTATING_HIGH_RISK.has(item.action?.type))) return null

  const actionTemplate = verified.slice(0, 24).map(item => ({
    action: { ...item.action },
    semanticAnchor: safeAnchor(item.semanticAnchor),
  }))
  if (actionTemplate.some(item => ['click_node', 'long_click_node', 'set_text', 'replace_text', 'clipboard_paste'].includes(item.action.type) && !item.semanticAnchor)) {
    return null
  }

  return {
    packageName: String(packageName).slice(0, 192),
    intentPattern: String(task.goal ?? '').toLowerCase().slice(0, 256),
    requiredCapabilities: [...new Set(actionTemplate.map(item => capabilityFor(item.action)))],
    actionTemplate,
    confidence: Math.min(0.95, 0.55 + verified.length * 0.08),
  }
}

function anchorMatches(node, anchor) {
  if (!node || !anchor) return false
  if (anchor.resourceId && node.resourceId === anchor.resourceId) return true
  if (anchor.text && node.text === anchor.text) return true
  if (anchor.contentDescription && node.contentDescription === anchor.contentDescription) return true
  return false
}

export function groundSkill(skill, observation) {
  if (!skill || !observation || skill.packageName !== observation.packageName) return null
  const nodes = Array.isArray(observation.nodes) ? observation.nodes : []
  const grounded = []

  for (const template of Array.isArray(skill.actionTemplate) ? skill.actionTemplate : []) {
    const action = { ...template.action }
    if (['click_node', 'long_click_node', 'set_text', 'replace_text', 'clipboard_paste'].includes(action.type)) {
      const node = nodes.find(candidate => candidate?.visibleToUser !== false && anchorMatches(candidate, template.semanticAnchor))
      if (!node?.nodeId) return null
      if (action.type === 'set_text' || action.type === 'replace_text' || action.type === 'clipboard_paste') action.selector = node.nodeId
      else action.selector = node.nodeId
    }
    grounded.push(action)
  }
  return grounded.length ? grounded : null
}
