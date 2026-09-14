import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('explicit negative constraints are retained for planner policy', () => {
  const intent = interpretTaskIntent('Play 2048 but do not buy anything')
  assert.ok(intent.userConstraints.length > 0)
})
