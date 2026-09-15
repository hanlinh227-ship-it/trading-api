import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('long-running intent includes a non-empty completion contract', () => {
  const intent = interpretTaskIntent('Keep working until the task is finished')
  assert.ok(intent.completionCriteria.length > 0)
})
