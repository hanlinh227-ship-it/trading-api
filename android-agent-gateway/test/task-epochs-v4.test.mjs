import test from 'node:test'
import assert from 'node:assert/strict'
import { createTaskState, recordTaskProgress } from '../src/task-policy.js'

test('long-running task progresses beyond 100 actions through checkpoints', () => {
  let task = createTaskState({
    taskId: 'long-1', goal: 'repeat until complete', capabilityScope: ['ui.navigate'],
    riskClass: 'A', taskRiskClass: 'A', persistence: 'LONG_RUNNING',
  })
  for (let i = 0; i < 125; i += 1) {
    task = recordTaskProgress(task, { kind: 'step', fingerprint: `f-${i}`, progressMarker: `p-${i}` })
  }
  assert.equal(task.stepCount, 125)
  assert.equal(task.epoch, 2)
  assert.equal(task.epochStepCount, 25)
  assert.equal(task.checkpointCount, 2)
})

test('ordinary long task is bounded at 20 epochs', () => {
  let task = createTaskState({
    taskId: 'long-cap', goal: 'repeat', capabilityScope: ['ui.navigate'],
    riskClass: 'A', taskRiskClass: 'A', persistence: 'LONG_RUNNING',
  })
  for (let i = 0; i < 1000; i += 1) {
    task = recordTaskProgress(task, { kind: 'step', fingerprint: `f-${i}`, progressMarker: `p-${i}` })
  }
  assert.throws(
    () => recordTaskProgress(task, { kind: 'step', fingerprint: 'overflow', progressMarker: 'overflow' }),
    /max_epochs/i,
  )
})

test('recovery limit remains five for the same unresolved state', () => {
  let task = createTaskState({
    taskId: 'recover', goal: 'navigate', capabilityScope: ['ui.navigate'],
    riskClass: 'A', taskRiskClass: 'A', persistence: 'LONG_RUNNING',
  })
  for (let i = 0; i < 5; i += 1) task = recordTaskProgress(task, { kind: 'recovery', fingerprint: 'same' })
  assert.throws(() => recordTaskProgress(task, { kind: 'recovery', fingerprint: 'same' }), /max_recoveries/i)
})
