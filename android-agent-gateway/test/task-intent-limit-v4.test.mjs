import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent output uses finite arrays', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.ok(intent.completionCriteria.length < 20)
  assert.ok(intent.forbiddenActions.length < 20)
})
