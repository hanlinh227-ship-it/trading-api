import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent capability scope has no duplicates', () => {
  const intent = interpretTaskIntent('Fill this form without submitting')
  assert.equal(intent.capabilityScope.length, new Set(intent.capabilityScope).size)
})
