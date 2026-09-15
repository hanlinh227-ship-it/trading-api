import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('one-shot task has one-shot completion criterion', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.ok(intent.completionCriteria.length > 0)
})
