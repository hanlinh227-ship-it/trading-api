import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('same goal yields stable intent fields', () => {
  const a = interpretTaskIntent('Open Settings')
  const b = interpretTaskIntent('Open Settings')
  assert.deepEqual(a, b)
})
