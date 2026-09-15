import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent, shouldUseTaskPath } from '../src/task-intent.js'

test('negated purchase becomes forbidden action without class C escalation', () => {
  const intent = interpretTaskIntent('Play 2048 until game over. Do not buy anything or open ads.')
  assert.equal(intent.riskClass, 'A')
  assert.equal(intent.persistence, 'UNTIL_TERMINAL')
  assert.equal(intent.executionMode, 'DETERMINISTIC')
  assert.ok(intent.forbiddenActions.includes('PURCHASE'))
  assert.ok(intent.forbiddenActions.includes('OPEN_AD'))
  assert.equal(shouldUseTaskPath(intent), true)
})

test('negated send/delete constraints are not requested mutations', () => {
  const intent = interpretTaskIntent('Open Messages and inspect spam. Do not send or delete anything.')
  assert.equal(intent.riskClass, 'A')
  assert.ok(intent.forbiddenActions.includes('SEND'))
  assert.ok(intent.forbiddenActions.includes('DELETE'))
})

test('explicit destructive and credential goals retain C and D risk', () => {
  assert.equal(interpretTaskIntent('Delete these 10 messages').riskClass, 'C')
  assert.equal(interpretTaskIntent('Send this message now').riskClass, 'C')
  assert.equal(interpretTaskIntent('Read my OTP and transfer money').riskClass, 'D')
})

test('ordinary one-shot navigation stays on legacy-compatible command path', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.equal(intent.persistence, 'ONE_SHOT')
  assert.equal(intent.executionMode, 'SEMANTIC')
  assert.equal(intent.riskClass, 'A')
  assert.equal(shouldUseTaskPath(intent), false)
})

test('repetitive and multi-step natural-language goals use task sessions', () => {
  assert.equal(shouldUseTaskPath(interpretTaskIntent('Keep scrolling until you reach the end')), true)
  assert.equal(shouldUseTaskPath(interpretTaskIntent('Open Gmail, find unread mail, then summarize the subjects')), true)
})
