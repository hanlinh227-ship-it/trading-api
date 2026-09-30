import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('play until I say stop maps to persistent user-stop policy', () => {
  const intent = interpretTaskIntent('Play this game until I tell you to stop')
  assert.equal(intent.persistencePolicy.includes('UNTIL_USER_STOP'), true)
  assert.equal(intent.persistencePolicy.includes('UNTIL_APP_SCOPE_EXIT'), true)
  assert.equal(intent.persistence, 'LONG_RUNNING')
})

test('ordinary bounded task keeps goal-complete policy', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.deepEqual(intent.persistencePolicy, ['UNTIL_GOAL_COMPLETE'])
})
