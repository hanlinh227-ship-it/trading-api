import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('risk matrix representative goals', () => {
  assert.equal(interpretTaskIntent('Open Settings').riskClass, 'A')
  assert.equal(interpretTaskIntent('Fill this form').riskClass, 'B')
  assert.equal(interpretTaskIntent('Delete this item').riskClass, 'C')
  assert.equal(interpretTaskIntent('Transfer money').riskClass, 'D')
})
