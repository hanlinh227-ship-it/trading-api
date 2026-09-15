import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('forbidden security-sensitive actions do not escalate a safe task', () => {
  const intent = interpretTaskIntent('Open Settings only. Do not read passwords, OTP codes, private keys, or sign any wallet.')
  assert.equal(intent.riskClass, 'A')
  assert.ok(intent.forbiddenActions.includes('CREDENTIAL_ACCESS'))
  assert.ok(intent.forbiddenActions.includes('WALLET_SIGN'))
})
