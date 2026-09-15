import test from 'node:test'
import assert from 'node:assert/strict'
import { planNextStep } from '../src/planner.js'

test('2048 deterministic task emits a swipe even when Workers AI is unavailable', async () => {
  const result = await planNextStep({
    env: {},
    task: {
      taskId: 'task-2048',
      goal: 'Play the currently visible 2048 game autonomously until game over.',
      capabilityScope: ['ui.navigate'],
      riskClass: 'A',
      taskRiskClass: 'A',
      deterministicAdapter: '2048',
      executionMode: 'DETERMINISTIC',
      persistence: 'UNTIL_TERMINAL',
      stepCount: 0,
      epoch: 0,
      recoveryCount: 0,
      forbiddenActions: ['PURCHASE', 'OPEN_AD', 'OPEN_EXTERNAL_LINK'],
    },
    observation: {
      screenWidth: 1080,
      screenHeight: 2400,
      screenshotAvailable: true,
      nodes: [],
    },
  })

  assert.equal(result.action.type, 'swipe')
  assert.equal(result.mode, 'deterministic-2048')
  assert.ok(result.action.startX >= 0 && result.action.startX <= 1080)
  assert.ok(result.action.endX >= 0 && result.action.endX <= 1080)
  assert.ok(result.action.startY >= 0 && result.action.startY <= 2400)
  assert.ok(result.action.endY >= 0 && result.action.endY <= 2400)
})

test('2048 deterministic swipe sequence changes with task progress to avoid dead directions', async () => {
  const make = async stepCount => planNextStep({
    env: {},
    task: {
      taskId: 'task-2048',
      goal: 'Play 2048',
      capabilityScope: ['ui.navigate'],
      riskClass: 'A',
      deterministicAdapter: '2048',
      executionMode: 'DETERMINISTIC',
      persistence: 'LONG_RUNNING',
      stepCount,
      forbiddenActions: [],
    },
    observation: { screenWidth: 1080, screenHeight: 2400, screenshotAvailable: true, nodes: [] },
  })

  const a = await make(0)
  const b = await make(1)
  assert.notDeepEqual(a.action, b.action)
})
