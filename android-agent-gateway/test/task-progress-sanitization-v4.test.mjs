import test from 'node:test'
import assert from 'node:assert/strict'
import { createTaskState, publicTaskState } from '../src/task-policy.js'

test('public V4 task state exposes progress metadata without private observations', () => {
  const task = createTaskState({
    taskId: 'pub1', goal: 'navigate', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A',
    persistence: 'LONG_RUNNING',
  })
  const publicState = publicTaskState({ ...task, privateObservation: { nodes: [{ text: 'secret' }] }, imageDataUrl: 'data:image/png;base64,abc' })
  assert.equal(publicState.taskId, 'pub1')
  assert.equal(publicState.persistence, 'LONG_RUNNING')
  assert.equal(typeof publicState.epoch, 'number')
  assert.equal('privateObservation' in publicState, false)
  assert.equal('imageDataUrl' in publicState, false)
})
