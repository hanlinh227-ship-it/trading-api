import test from 'node:test'
import assert from 'node:assert/strict'
import { bridgeDispatchPlan } from '../src/task-intent.js'

test('bridge dispatches 2048 autopilot through schema-2 tasks', () => {
  const plan = bridgeDispatchPlan('Play the currently open 2048 game autonomously until game over')
  assert.equal(plan.path, 'tasks')
  assert.equal(plan.schema, 2)
  assert.equal(plan.intent.deterministicAdapter, '2048')
})

test('bridge keeps safe one-shot open-app command backward compatible', () => {
  const plan = bridgeDispatchPlan('Open Settings')
  assert.equal(plan.path, 'commands')
  assert.equal(plan.schema, 1)
})
