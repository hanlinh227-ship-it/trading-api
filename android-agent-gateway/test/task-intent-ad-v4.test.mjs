import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('explicit no-ad constraint is preserved for game autopilot', () => {
  const intent = interpretTaskIntent('Play until game over; do not interact with ads or external links')
  assert.ok(intent.forbiddenActions.includes('OPEN_AD'))
  assert.ok(intent.forbiddenActions.includes('OPEN_EXTERNAL_LINK'))
})
