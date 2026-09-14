import test from 'node:test'
import assert from 'node:assert/strict'
import { bridgeDispatchPlan } from '../src/task-intent.js'

test('bridge plan exposes interpreted intent', () => {
  const plan = bridgeDispatchPlan('Open Settings')
  assert.equal(plan.intent.objective, 'Open Settings')
})
