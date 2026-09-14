import test from 'node:test'
import assert from 'node:assert/strict'
import { bridgeDispatchPlan } from '../src/task-intent.js'

test('long execution bridge plan is schema 2', () => {
  assert.equal(bridgeDispatchPlan('Keep working until finished').schema, 2)
})
