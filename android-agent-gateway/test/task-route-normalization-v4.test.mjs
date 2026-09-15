import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizedTaskInput } from '../src/index.js'

test('task input carries structured V4 intent and safe scope', () => {
  const task = normalizedTaskInput({
    goal: 'Play 2048 until game over. Do not buy anything.',
    capabilityScope: ['ui.navigate'],
  }, 'github-oidc')
  assert.equal(task.taskRiskClass, 'A')
  assert.equal(task.persistence, 'UNTIL_TERMINAL')
  assert.equal(task.executionMode, 'DETERMINISTIC')
  assert.equal(task.deterministicAdapter, '2048')
  assert.ok(task.forbiddenActions.includes('PURCHASE'))
})
