import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('forbidden actions are deduplicated', () => {
  const intent = interpretTaskIntent('Do not buy, do not purchase, do not buy anything')
  assert.equal(intent.forbiddenActions.length, new Set(intent.forbiddenActions).size)
})
