import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('simple open command is one shot', () => {
  assert.equal(interpretTaskIntent('Open Settings').persistence, 'ONE_SHOT')
})
