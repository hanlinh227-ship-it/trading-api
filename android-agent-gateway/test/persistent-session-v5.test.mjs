import test from 'node:test'
import assert from 'node:assert/strict'
import { createTaskState, recordTaskProgress } from '../src/task-policy.js'

test('until-user-stop task rolls beyond legacy 1000-action ceiling', () => {
  let task = createTaskState({
    taskId: 'persistent-v5',
    goal: 'keep playing until I say stop',
    capabilityScope: ['ui.navigate'],
    riskClass: 'A',
    taskRiskClass: 'A',
    persistence: 'LONG_RUNNING',
    persistencePolicy: ['UNTIL_USER_STOP', 'UNTIL_APP_SCOPE_EXIT'],
  })
  for (let i = 0; i < 1050; i += 1) {
    task = recordTaskProgress(task, {
      kind: 'step',
      fingerprint: `fp-${i}`,
      progressMarker: `progress-${i}`,
      status: 'PLANNING',
    })
  }
  assert.equal(task.stepCount, 1050)
  assert.equal(task.epoch, 21)
  assert.equal(task.status, 'PLANNING')
})

test('bounded task retains legacy epoch ceiling', () => {
  let task = createTaskState({
    taskId: 'bounded',
    goal: 'bounded task',
    capabilityScope: ['ui.navigate'],
    riskClass: 'A',
    taskRiskClass: 'A',
    persistence: 'LONG_RUNNING',
    persistencePolicy: ['UNTIL_GOAL_COMPLETE'],
    stepCount: 1000,
    epoch: 20,
  })
  assert.throws(() => recordTaskProgress(task, { kind: 'step', progressMarker: 'x' }), /max_epochs_exceeded/)
})
