import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('long-running task does not gain destructive scope automatically', () => {
  const intent = interpretTaskIntent('Keep scrolling until you reach the end')
  assert.equal(intent.capabilityScope.includes('ui.destructive.confirmed'), false)
})
