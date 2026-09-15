import test from 'node:test'
import assert from 'node:assert/strict'
import { bridgeDispatchPlan } from '../src/task-intent.js'

test('one-shot bridge plan is schema 1', () => {
  assert.equal(bridgeDispatchPlan('Open Settings').schema, 1)
})
