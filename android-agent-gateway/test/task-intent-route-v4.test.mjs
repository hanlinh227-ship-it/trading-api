import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent, shouldUseTaskPath } from '../src/task-intent.js'

test('reversible setting change is class B task session', () => {
  const intent = interpretTaskIntent('Change dark mode')
  assert.equal(intent.riskClass, 'B')
  assert.ok(intent.capabilityScope.includes('ui.write'))
  assert.equal(shouldUseTaskPath(intent), true)
})
