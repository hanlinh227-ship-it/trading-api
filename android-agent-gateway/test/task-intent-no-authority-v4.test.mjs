import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('forbidden purchase does not grant destructive capability', () => {
  const intent = interpretTaskIntent('Do not purchase anything; just inspect the screen')
  assert.equal(intent.capabilityScope.includes('ui.destructive.confirmed'), false)
})
