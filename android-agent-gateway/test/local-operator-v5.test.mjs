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
  const token = 'device-token-local-v5'
  const task = createTaskState({
    taskId: 'task-local-v5',
    goal: 'navigate safely until complete',
    capabilityScope: ['ui.navigate'],
    riskClass: 'A',
    taskRiskClass: 'A',
    persistence: 'LONG_RUNNING',
    persistencePolicy: ['UNTIL_GOAL_COMPLETE'],
    allowedPackages: ['com.example'],
  })
  const values = new Map([
    ['pairing', { paired: true, deviceId: 'device-local-v5', deviceTokenHash: await sha256Base64(token) }],
    ['task:task-local-v5', { ...task, history: [] }],
    ['queue', []],
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

test('local operator continuation returns bounded actions without enqueuing a signed per-action command', async () => {
  const { token, values, session } = await fixture()
  const response = await session.fetch(new Request('https://device.internal/task-step', {
    method: 'POST',
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({
      taskId: 'task-local-v5',
      localOperator: true,
      observation: { packageName: 'com.example', fingerprint: 'fp-1', nodes: [] },
    }),
  }))

  assert.equal(response.status, 200)
  const body = await response.json()
  assert.ok(Array.isArray(body.localActions))
  assert.ok(body.localActions.length > 0 && body.localActions.length <= 8)
  assert.equal(typeof body.localBatchId, 'string')
  assert.deepEqual(values.get('queue'), [])
  assert.equal(values.get('task:task-local-v5').pendingCommandId, body.localBatchId)
  assert.deepEqual(body.capabilityScope, ['ui.navigate'])
  assert.deepEqual(body.allowedPackages, ['com.example'])
})
