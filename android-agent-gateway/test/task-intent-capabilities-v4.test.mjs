import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('typing goal requests ui.write while safe navigation does not', () => {
  const typing = interpretTaskIntent('Fill this form but do not submit it')
  assert.equal(typing.riskClass, 'B')
  assert.ok(typing.capabilityScope.includes('ui.write'))
  assert.ok(typing.forbiddenActions.includes('SEND'))

  const nav = interpretTaskIntent('Open Settings')
  assert.equal(nav.capabilityScope.includes('ui.write'), false)
})
