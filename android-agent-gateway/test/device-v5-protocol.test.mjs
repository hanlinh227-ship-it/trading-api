import test from 'node:test'
import assert from 'node:assert/strict'
import { DeviceSession } from '../src/device-session.js'
import { createTaskState } from '../src/task-policy.js'

async function sha256Base64(value) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  let binary = ''
  for (const b of new Uint8Array(digest)) binary += String.fromCharCode(b)
  return btoa(binary)
}

async function fixture() {
  const token = 'device-token-v5'
  const task = createTaskState({
    taskId: 'task-v5',
    goal: 'navigate safely until complete',
    capabilityScope: ['ui.navigate'],
    riskClass: 'A',
    taskRiskClass: 'A',
    persistence: 'LONG_RUNNING',
    persistencePolicy: ['UNTIL_GOAL_COMPLETE'],
    allowedPackages: ['com.example'],
  })
  const values = new Map([
    ['pairing', { paired: true, deviceId: 'device-v5', deviceTokenHash: await sha256Base64(token) }],
    ['task:task-v5', { ...task, history: [] }],
  ])
  const state = {
    storage: {
      get: async key => values.get(key),
      put: async (key, value) => values.set(key, value),
    },
    getWebSockets: () => [],
  }
  return { token, values, session: new DeviceSession(state, {}) }
}

function request(path, token, body = {}) {
  return new Request(`https://device.internal${path}`, {
    method: 'POST',
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

test('device checkpoint stores only sanitized bounded metadata', async () => {
  const { token, values, session } = await fixture()
  const response = await session.fetch(request('/task-checkpoint/task-v5', token, {
    stepCount: 17,
    epoch: 2,
    checkpointCount: 4,
    screenSignature: 'screen-safe',
    selectedSkillId: 'settings-navigation',
    screenshot: 'PRIVATE_IMAGE',
    rawPrompt: 'PRIVATE_PROMPT',
    metrics: { verifierLatencyMs: 7, rawPrompt: 'PRIVATE' },
  }))
  assert.equal(response.status, 200)
  const task = values.get('task:task-v5')
  assert.equal(task.lastDeviceCheckpoint.stepCount, 17)
  assert.equal(task.lastDeviceCheckpoint.screenSignature, 'screen-safe')
  assert.equal(task.lastDeviceCheckpoint.metrics.verifierLatencyMs, 7)
  assert.equal(task.lastDeviceCheckpoint.screenshot, undefined)
  assert.equal(task.lastDeviceCheckpoint.rawPrompt, undefined)
  assert.equal(task.lastDeviceCheckpoint.metrics.rawPrompt, undefined)
})

test('checkpoint and cloud escalation endpoints require paired device token', async () => {
  const { session } = await fixture()
  for (const path of ['/task-checkpoint/task-v5', '/task-micro-plan/task-v5', '/task-recovery/task-v5']) {
    const response = await session.fetch(request(path, 'wrong-token', { observation: {} }))
    assert.equal(response.status, 401, path)
  }
})

test('micro-plan returns bounded typed actions without widening task scope', async () => {
  const { token, session } = await fixture()
  const response = await session.fetch(request('/task-micro-plan/task-v5', token, {
    observation: { packageName: 'com.example', fingerprint: 'fp-1', nodes: [] },
    maxActions: 8,
  }))
  assert.equal(response.status, 200)
  const body = await response.json()
  assert.ok(Array.isArray(body.actions))
  assert.ok(body.actions.length <= 8)
  assert.deepEqual(body.actions, [{ type: 'read_screen' }])
  assert.deepEqual(body.task.persistencePolicy, ['UNTIL_GOAL_COMPLETE'])
  assert.deepEqual(body.task.allowedPackages, ['com.example'])
  assert.deepEqual(body.task.capabilityScope, ['ui.navigate'])
  assert.equal(body.task.riskClass, 'A')
})

test('recovery endpoint is bounded and records only sanitized recovery reason', async () => {
  const { token, values, session } = await fixture()
  const response = await session.fetch(request('/task-recovery/task-v5', token, {
    observation: { packageName: 'com.example', fingerprint: 'fp-2', nodes: [] },
    reason: 'LOCAL_POSTCONDITION_NOT_MET <private body>',
  }))
  assert.equal(response.status, 200)
  const body = await response.json()
  assert.ok(Array.isArray(body.actions))
  assert.ok(body.actions.length <= 8)
  const task = values.get('task:task-v5')
  assert.match(task.lastRecoveryReason, /^[A-Za-z0-9_.:-]+$/)
  assert.ok(task.lastRecoveryReason.length <= 96)
})
