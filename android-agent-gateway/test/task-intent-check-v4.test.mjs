import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('2048 autopilot does not request write/destructive capability', () => {
  const intent = interpretTaskIntent('Play 2048 until game over')
  assert.deepEqual(intent.capabilityScope, ['ui.navigate'])
})
