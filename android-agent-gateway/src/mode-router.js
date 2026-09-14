const MODES = new Set(['AUTO', 'SEMANTIC', 'VISUAL', 'HYBRID', 'DETERMINISTIC'])

export function selectExecutionMode(intent = {}, observation = {}) {
  const requested = MODES.has(intent.executionMode) ? intent.executionMode : 'AUTO'
  if (requested !== 'AUTO') return requested

  if (intent.deterministicAdapter) return 'DETERMINISTIC'

  const nodes = Array.isArray(observation.nodes) ? observation.nodes : []
  const semanticUseful = nodes.some(node => node && node.visibleToUser !== false && (
    node.clickable === true || node.editable === true || node.scrollable === true ||
    typeof node.text === 'string' || typeof node.contentDescription === 'string'
  ))
  const screenshotAvailable = observation.screenshotAvailable === true

  if (intent.gameLike === true || /game|puzzle|canvas|surfaceview/i.test(String(intent.objective ?? ''))) {
    return semanticUseful && screenshotAvailable ? 'HYBRID' : screenshotAvailable ? 'VISUAL' : 'SEMANTIC'
  }
  if (semanticUseful) return 'SEMANTIC'
  if (screenshotAvailable) return 'VISUAL'
  return 'SEMANTIC'
}
