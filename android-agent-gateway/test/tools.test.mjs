import test from 'node:test'
import assert from 'node:assert/strict'
import { validateRunGoal, classifyGoal } from '../src/tools.js'

test('raw shell is never accepted by android_run_goal', () => {
  assert.throws(() => validateRunGoal({ deviceId: 'd1', goal: 'x', rawShell: 'rm -rf /' }))
})

test('normal goal validates and defaults to class A', () => {
  const input = validateRunGoal({ deviceId: 'd1', goal: 'Open Settings' })
  assert.equal(input.deviceId, 'd1')
  assert.equal(classifyGoal(input.goal), 'A')
})

test('financial credential goals are class D blocked', () => {
  assert.equal(classifyGoal('read my OTP and transfer money'), 'D')
})

test('destructive goal remains class C and can carry explicit confirmation', () => {
  const input = validateRunGoal({
    deviceId: 'd1',
    goal: 'Xóa những tin nhắn rác trong phần tin nhắn',
    confirmedRiskClassC: true,
  })
  assert.equal(classifyGoal(input.goal), 'C')
  assert.equal(input.confirmedRiskClassC, true)
})

test('typing and drafting are class B but sending is class C', () => {
  assert.equal(classifyGoal('type hello into the message box'), 'B')
  assert.equal(classifyGoal('soạn nháp lời chào nhưng chưa gửi'), 'B')
  assert.equal(classifyGoal('send message to Linh'), 'C')
  assert.equal(classifyGoal('gửi tin nhắn cho Linh'), 'C')
})
