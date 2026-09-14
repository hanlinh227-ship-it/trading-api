import test from 'node:test'
import assert from 'node:assert/strict'
import { healthPayload, normalizedTaskInput } from '../src/index.js'

test('health advertises schema-2 task capability without private data', () => {
  const health = healthPayload({ DEPLOYMENT_SOURCE_SHA: 'abc123', AI: {} })
  assert.equal(health.ok, true)
  assert.equal(health.taskSchema, 2)
  assert.equal(health.plannerMode, 'workers-ai-with-deterministic-fallback')
  assert.equal(health.capabilities?.ephemeralScreenshots, true)
  assert.equal(health.capabilities?.localContacts, true)
  assert.equal('observation' in health, false)
  assert.equal('screenshot' in health, false)
})

test('class B task defaults include signed ui.write scope and preserve task risk floor', () => {
  const task = normalizedTaskInput({ goal: 'Type a draft reply' }, 'github-oidc')
  assert.equal(task.taskRiskClass, 'B')
  assert.equal(task.riskClass, 'B')
  assert.ok(task.capabilityScope.includes('ui.navigate'))
  assert.ok(task.capabilityScope.includes('ui.write'))
  assert.equal(task.confirmedRiskClassC, false)
})

test('class C task confirmation is task-bound and default scope includes destructive authority', () => {
  const task = normalizedTaskInput({ goal: 'Delete the selected conversation', confirmedRiskClassC: true }, 'github-oidc')
  assert.equal(task.taskRiskClass, 'C')
  assert.equal(task.riskClass, 'C')
  assert.equal(task.confirmedTaskId, task.taskId)
  assert.ok(task.capabilityScope.includes('ui.destructive.confirmed'))
})

test('class D task stays blocked even with a higher requested ceiling', () => {
  assert.throws(
    () => normalizedTaskInput({ goal: 'Read OTP and transfer money', riskCeiling: 'C' }, 'github-oidc'),
    /class_d_blocked/,
  )
})
