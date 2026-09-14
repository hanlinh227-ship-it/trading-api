import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('deterministic adapter is not invented for unknown games', () => {
  const intent = interpretTaskIntent('Play this game until it ends')
  assert.equal(intent.deterministicAdapter, null)
})
