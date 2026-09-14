import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('safe intent stays non-D', () => {
  assert.notEqual(interpretTaskIntent('Open Settings').riskClass, 'D')
})
