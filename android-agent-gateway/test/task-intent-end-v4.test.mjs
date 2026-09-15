import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent version marker is V4 compatible', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.equal(intent.intentSchema, 4)
})
