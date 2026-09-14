import test from 'node:test'
import assert from 'node:assert/strict'
import { DeviceSession } from '../src/device-session.js'

function memoryState() {
  const values = new Map()
  return {
    values,
    state: {
      storage: {
        get: async key => values.get(key),
        put: async (key, value) => values.set(key, value),
      },
      getWebSockets: () => [],
    },
  }
}

test('device durable object creates and reads a bounded V3 task', async () => {
  const { state } = memoryState()
  const session = new DeviceSession(state, {})
  const created = await session.fetch(new Request('https://device.internal/task', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      taskId: 'task-1',
      goal: 'Open Settings and inspect display options',
      capabilityScope: ['apps.open', 'ui.navigate'],
      riskClass: 'A',
      confirmedRiskClassC: false,
    }),
  }))
  assert.equal(created.status, 201)
  const body = await created.json()
  assert.equal(body.taskId, 'task-1')
  assert.equal(body.status, 'QUEUED')
  assert.equal(body.stepCount, 0)
  assert.equal(body.recoveryCount, 0)

  const fetched = await session.fetch(new Request('https://device.internal/task/task-1'))
  assert.equal(fetched.status, 200)
  assert.equal((await fetched.json()).goal, 'Open Settings and inspect display options')
})

test('missing task returns 404 without leaking other state', async () => {
  const { state } = memoryState()
  const session = new DeviceSession(state, {})
  const response = await session.fetch(new Request('https://device.internal/task/missing'))
  assert.equal(response.status, 404)
  assert.deepEqual(await response.json(), { error: 'task_not_found' })
})
