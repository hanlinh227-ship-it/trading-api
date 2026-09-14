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

async function tokenHash(token) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token)))
  let binary = ''
  for (const b of digest) binary += String.fromCharCode(b)
  return btoa(binary)
}

async function pairedSession(aiRun) {
  const { state, values } = memoryState()
  values.set('pairing', {
    paired: true,
    deviceId: 'device-1',
    deviceTokenHash: await tokenHash('device-token'),
  })
  const session = new DeviceSession(state, { AI: { run: aiRun } })
  const created = await session.fetch(new Request('https://device.internal/task', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      taskId: 'task-1',
      goal: 'Navigate settings',
      capabilityScope: ['apps.open', 'ui.navigate'],
      riskClass: 'A',
      confirmedRiskClassC: false,
    }),
  }))
  assert.equal(created.status, 201)
  return { session, values }
}

function taskStepRequest(body) {
  return new Request('https://device.internal/task-step', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: 'Bearer device-token',
    },
    body: JSON.stringify(body),
  })
}

test('authenticated observation plans one signed schema-2 command', async () => {
  const { session } = await pairedSession(async () => ({
    response: JSON.stringify({
      action: { type: 'global_back' },
      expected: { type: 'observation_changed' },
      rationaleCode: 'BACK_ONE_SCREEN',
    }),
  }))

  const response = await session.fetch(taskStepRequest({
    taskId: 'task-1',
    observation: { packageName: 'com.android.settings', fingerprint: 'fp-1', nodes: [] },
    previousResult: null,
  }))
  assert.equal(response.status, 202)
  const planned = await response.json()
  assert.equal(planned.status, 'ACTING')
  assert.equal(planned.plannerMode, 'workers-ai')

  const next = await session.fetch(new Request('https://device.internal/next', {
    headers: { authorization: 'Bearer device-token' },
  }))
  const command = (await next.json()).command
  assert.equal(command.schema, 2)
  assert.equal(command.taskId, 'task-1')
  assert.deepEqual(command.action, { type: 'global_back' })
  assert.equal(command.riskClass, 'A')
  assert.ok(command.signature)
})

test('ephemeral screenshot is never retained in durable state', async () => {
  const { session, values } = await pairedSession(async () => ({
    response: JSON.stringify({
      action: { type: 'global_back' },
      expected: { type: 'observation_changed' },
      rationaleCode: 'SAFE_BACK',
    }),
  }))
  const secretImage = 'data:image/jpeg;base64,VERY_PRIVATE_SCREENSHOT_BYTES'
  const response = await session.fetch(taskStepRequest({
    taskId: 'task-1',
    observation: { packageName: 'com.example', fingerprint: 'fp-2', nodes: [] },
    imageDataUrl: secretImage,
    previousResult: null,
  }))
  assert.equal(response.status, 202)
  assert.equal(JSON.stringify([...values.entries()]).includes('VERY_PRIVATE_SCREENSHOT_BYTES'), false)
})

test('planner completion closes task without queueing another action', async () => {
  const { session } = await pairedSession(async () => ({
    response: JSON.stringify({
      action: { type: 'read_screen' },
      expected: { type: 'task_complete' },
      rationaleCode: 'GOAL_SATISFIED',
    }),
  }))
  const response = await session.fetch(taskStepRequest({
    taskId: 'task-1',
    observation: { packageName: 'com.example', fingerprint: 'fp-done', nodes: [] },
    previousResult: null,
  }))
  assert.equal(response.status, 200)
  assert.equal((await response.json()).status, 'COMPLETED')

  const next = await session.fetch(new Request('https://device.internal/next', {
    headers: { authorization: 'Bearer device-token' },
  }))
  assert.equal((await next.json()).command, null)
})

test('failed previous action increments bounded recovery before replanning', async () => {
  const { session } = await pairedSession(async () => ({
    response: JSON.stringify({
      action: { type: 'read_screen' },
      expected: { type: 'observation_returned' },
      rationaleCode: 'RECOVER_OBSERVE',
    }),
  }))
  const response = await session.fetch(taskStepRequest({
    taskId: 'task-1',
    observation: { packageName: 'com.example', fingerprint: 'fp-r', nodes: [] },
    previousResult: { status: 'FAILED', code: 'ACTION_DISPATCH_FAILED' },
  }))
  assert.equal(response.status, 202)
  const body = await response.json()
  assert.equal(body.recoveryCount, 1)
})

test('task-step requires authenticated paired device', async () => {
  const { state } = memoryState()
  const session = new DeviceSession(state, {})
  const response = await session.fetch(taskStepRequest({ taskId: 'missing', observation: {} }))
  assert.equal(response.status, 401)
  assert.deepEqual(await response.json(), { error: 'unauthorized_device' })
})
