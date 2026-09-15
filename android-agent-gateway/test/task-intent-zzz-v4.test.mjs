import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('until game over remains terminal persistence', () => {
  assert.equal(interpretTaskIntent('Play until game over').persistence, 'UNTIL_TERMINAL')
})
