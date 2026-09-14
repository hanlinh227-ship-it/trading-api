import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('until-terminal game intent includes terminal completion criteria', () => {
  const intent = interpretTaskIntent('Play 2048 until game over')
  assert.ok(intent.completionCriteria.includes('GAME_TERMINAL'))
  assert.equal(intent.persistence, 'UNTIL_TERMINAL')
})
