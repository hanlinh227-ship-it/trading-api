import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('repeat-until-complete intent becomes long-running task', () => {
  const intent = interpretTaskIntent('Do the repetitive steps until the work is finished')
  assert.equal(intent.persistence, 'LONG_RUNNING')
  assert.equal(intent.riskClass, 'A')
})
