import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('external links can be explicitly forbidden without risk escalation', () => {
  const intent = interpretTaskIntent('Play this game; do not open external links')
  assert.equal(intent.riskClass, 'A')
  assert.ok(intent.forbiddenActions.includes('OPEN_EXTERNAL_LINK'))
})
