import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent, shouldUseTaskPath } from '../src/task-intent.js'

test('safe multi-step inspect uses task session even at class A', () => {
  const intent = interpretTaskIntent('Open Messages, inspect spam, then go back home')
  assert.equal(intent.riskClass, 'A')
  assert.equal(shouldUseTaskPath(intent), true)
})
