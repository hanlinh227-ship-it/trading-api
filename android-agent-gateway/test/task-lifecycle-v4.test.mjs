import test from 'node:test'
import assert from 'node:assert/strict'
import { createTaskState, confirmTaskState, cancelTaskState } from '../src/task-policy.js'

test('class C confirmation is bound to the exact task id', () => {
  const task = createTaskState({
    taskId: 'c1', goal: 'delete selected messages', capabilityScope: ['ui.navigate', 'ui.destructive.confirmed'],
    riskClass: 'C', taskRiskClass: 'C', persistence: 'LONG_RUNNING',
  })
  const confirmed = confirmTaskState(task, 'c1')
  assert.equal(confirmed.confirmedRiskClassC, true)
  assert.equal(confirmed.confirmedTaskId, 'c1')
  assert.throws(() => confirmTaskState(task, 'other'), /task_confirmation_mismatch/i)
})

test('cancel is terminal and sanitized', () => {
  const task = createTaskState({
    taskId: 'a1', goal: 'navigate', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A', persistence: 'LONG_RUNNING',
  })
  const cancelled = cancelTaskState(task)
  assert.equal(cancelled.status, 'CANCELLED')
  assert.equal(cancelled.failureCode, 'USER_CANCELLED')
})
