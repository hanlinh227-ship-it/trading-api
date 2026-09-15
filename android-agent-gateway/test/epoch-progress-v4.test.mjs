import test from 'node:test'
import assert from 'node:assert/strict'
import { createTaskState, recordTaskProgress } from '../src/task-policy.js'

test('until-terminal epoch extension requires changing progress markers', () => {
  let task = createTaskState({
    taskId: 'game1', goal: 'play until game over', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A',
    persistence: 'UNTIL_TERMINAL',
  })
  for (let i = 0; i < 50; i += 1) {
    task = recordTaskProgress(task, { kind: 'step', fingerprint: `f-${i}`, progressMarker: `score-${i}` })
  }
  assert.equal(task.epoch, 1)
  assert.equal(task.checkpointCount, 1)

  let stalled = createTaskState({
    taskId: 'game2', goal: 'play until game over', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A',
    persistence: 'UNTIL_TERMINAL',
  })
  for (let i = 0; i < 50; i += 1) {
    stalled = recordTaskProgress(stalled, { kind: 'step', fingerprint: 'same', progressMarker: 'same' })
  }
  assert.throws(
    () => recordTaskProgress(stalled, { kind: 'step', fingerprint: 'same', progressMarker: 'same' }),
    /no_progress/i,
  )
})
