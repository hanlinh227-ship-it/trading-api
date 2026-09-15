const STRATEGY = ['LEFT', 'DOWN', 'LEFT', 'DOWN', 'RIGHT', 'DOWN']
const RECOVERY = ['LEFT', 'DOWN', 'RIGHT', 'UP']
const MAX_BOUNDED_SWIPES = 900

function dimension(value, fallback) {
  return Number.isInteger(value) && value > 0 ? value : fallback
}

function point(value, min, max) {
  return Math.max(min, Math.min(max, Math.round(value)))
}

function terminalText(observation) {
  const nodes = Array.isArray(observation?.nodes) ? observation.nodes : []
  return nodes.some(node => {
    const text = `${node?.text ?? ''} ${node?.contentDescription ?? ''}`.toLowerCase()
    return /\bgame\s*over\b|\bno\s+more\s+moves\b|trò\s*chơi\s*kết\s*thúc|hết\s*nước\s*đi/u.test(text)
  })
}

function swipeFor(direction, width, height) {
  const left = point(width * 0.20, 1, width - 1)
  const right = point(width * 0.80, 1, width - 1)
  const middleX = point(width * 0.50, 1, width - 1)
  const middleY = point(height * 0.55, 1, height - 1)
  const top = point(height * 0.36, 1, height - 1)
  const bottom = point(height * 0.74, 1, height - 1)

  switch (direction) {
    case 'LEFT':
      return { type: 'swipe', startX: right, startY: middleY, endX: left, endY: middleY, durationMs: 180 }
    case 'RIGHT':
      return { type: 'swipe', startX: left, startY: middleY, endX: right, endY: middleY, durationMs: 180 }
    case 'UP':
      return { type: 'swipe', startX: middleX, startY: bottom, endX: middleX, endY: top, durationMs: 180 }
    default:
      return { type: 'swipe', startX: middleX, startY: top, endX: middleX, endY: bottom, durationMs: 180 }
  }
}

export function plan2048Step(task = {}, observation = {}) {
  const stepCount = Number.isInteger(task.stepCount) ? task.stepCount : 0
  if (terminalText(observation) || stepCount >= MAX_BOUNDED_SWIPES) {
    return {
      action: { type: 'read_screen' },
      expectedPostcondition: { type: 'task_complete' },
      requiredCapabilities: ['ui.navigate'],
      riskClass: 'A',
      direction: null,
    }
  }

  // Canvas/WebView games can move visually while exposing an unchanged Accessibility tree.
  // Do not treat that semantic no-change as a failed swipe. The task remains bounded and
  // explicit game-over text still terminates immediately when the app exposes it.
  const recoveryCount = Number.isInteger(task.recoveryCount) ? task.recoveryCount : 0
  const direction = recoveryCount > 0
    ? RECOVERY[(stepCount + recoveryCount) % RECOVERY.length]
    : STRATEGY[stepCount % STRATEGY.length]
  const width = dimension(observation?.screenWidth, 1080)
  const height = dimension(observation?.screenHeight, 2400)

  return {
    action: swipeFor(direction, width, height),
    expectedPostcondition: { type: 'observation_returned' },
    requiredCapabilities: ['ui.navigate'],
    riskClass: 'A',
    direction,
  }
}
