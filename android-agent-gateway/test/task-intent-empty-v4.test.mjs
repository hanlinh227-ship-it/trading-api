import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('empty task intent is rejected', () => {
  assert.throws(() => interpretTaskIntent('   '), /goal_required/i)
})
