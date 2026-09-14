import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('simple back navigation remains one-shot semantic action', () => {
  const intent = interpretTaskIntent('Go back once')
  assert.equal(intent.persistence, 'ONE_SHOT')
  assert.equal(intent.executionMode, 'SEMANTIC')
  assert.equal(intent.riskClass, 'A')
})
