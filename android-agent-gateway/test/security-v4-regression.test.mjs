import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'
import { clampTaskStep, createTaskState } from '../src/task-policy.js'

test('V4 never converts forbidden credential or financial actions into executable authority', () => {
  const intent = interpretTaskIntent('Never read my OTP, never sign a wallet, and just open Settings')
  assert.equal(intent.riskClass, 'A')
  assert.ok(intent.forbiddenActions.includes('CREDENTIAL_ACCESS'))
  assert.ok(intent.forbiddenActions.includes('WALLET_SIGN'))
})

test('actual wallet signing action stays denied even under a broad task ceiling', () => {
  const task = createTaskState({
    taskId: 'd-deny', goal: 'safe task', capabilityScope: ['ui.navigate', 'security.denied'],
    riskClass: 'C', taskRiskClass: 'A', persistence: 'LONG_RUNNING',
  })
  assert.throws(() => clampTaskStep({ task, action: { type: 'wallet_sign', payload: 'x' } }), /class_d_denied/i)
})
