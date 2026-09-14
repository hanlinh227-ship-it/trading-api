import test from 'node:test'
import assert from 'node:assert/strict'
import { shouldUseTaskPath, interpretTaskIntent } from '../src/task-intent.js'

test('games always use task path', () => {
  assert.equal(shouldUseTaskPath(interpretTaskIntent('Play this game')), true)
})
