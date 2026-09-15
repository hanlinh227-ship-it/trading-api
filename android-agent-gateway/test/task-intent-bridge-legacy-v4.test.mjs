import test from 'node:test'
import assert from 'node:assert/strict'
import { bridgeDispatchPlan } from '../src/task-intent.js'

test('class B editing never uses legacy command path', () => {
  assert.equal(bridgeDispatchPlan('Fill this form').path, 'tasks')
})
