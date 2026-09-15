import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('constraints remain visible to planner', () => {
  assert.ok(interpretTaskIntent('Do not buy anything').userConstraints.length > 0)
})
