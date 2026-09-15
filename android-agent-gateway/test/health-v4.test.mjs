import test from 'node:test'
import assert from 'node:assert/strict'
import { healthPayload } from '../src/index.js'

test('gateway health advertises V4 task-first long horizon and deterministic game support', () => {
  const health = healthPayload({ AI: { run() {} } })
  assert.equal(health.taskSchema, 2)
  assert.equal(health.capabilities.taskFirstBridge, true)
  assert.equal(health.capabilities.longHorizonEpochs, true)
  assert.equal(health.capabilities.hybridPerception, true)
  assert.equal(health.capabilities.appSkillMemory, true)
  assert.equal(health.capabilities.game2048Deterministic, true)
  assert.equal(health.capabilities.rawShell, undefined)
  assert.equal(health.rawShell, false)
})
