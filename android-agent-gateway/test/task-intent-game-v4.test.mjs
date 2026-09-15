import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('generic non-2048 game intent requests visual long-running task without deterministic adapter', () => {
  const intent = interpretTaskIntent('Play this puzzle game until it ends')
  assert.equal(intent.persistence, 'UNTIL_TERMINAL')
  assert.equal(intent.executionMode, 'VISUAL')
  assert.equal(intent.deterministicAdapter, null)
  assert.equal(intent.riskClass, 'A')
})
