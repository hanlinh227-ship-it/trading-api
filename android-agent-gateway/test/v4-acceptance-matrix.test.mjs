import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent, shouldUseTaskPath } from '../src/task-intent.js'
import { selectExecutionMode } from '../src/mode-router.js'

test('V4 acceptance matrix classifies representative phone workflows', () => {
  const cases = [
    ['Open Settings', 'A', false],
    ['Read the Android version', 'A', false],
    ['Change dark mode', 'B', true],
    ['Fill this form but do not submit it', 'B', true],
    ['Keep scrolling until you reach the end', 'A', true],
    ['Play 2048 until game over and do not buy anything', 'A', true],
  ]
  for (const [goal, risk, taskPath] of cases) {
    const intent = interpretTaskIntent(goal)
    assert.equal(intent.riskClass, risk, goal)
    assert.equal(shouldUseTaskPath(intent), taskPath, goal)
  }
})

test('visual custom UI can use screenshot fallback without widening risk', () => {
  const intent = interpretTaskIntent('Inspect this custom game screen')
  const mode = selectExecutionMode(intent, { nodes: [], screenshotAvailable: true, packageName: 'com.example.game' })
  assert.equal(mode, 'VISUAL')
  assert.equal(intent.riskClass, 'A')
})
