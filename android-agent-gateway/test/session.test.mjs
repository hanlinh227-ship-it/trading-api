import test from 'node:test'
import assert from 'node:assert/strict'
import { DeviceSession, isDeviceOnline, pruneExpiredCommands, validateCommandForQueue } from '../src/device-session.js'

async function sha256Base64(value) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  let binary = ''
  for (const b of new Uint8Array(digest)) binary += String.fromCharCode(b)
  return btoa(binary)
}

test('expired commands are rejected before queueing', () => {
  assert.throws(() => validateCommandForQueue({
    schema: 1,
    commandId: 'c1',
    deviceId: 'd1',
    issuedAt: '2026-09-14T03:00:00Z',
    expiresAt: '2026-09-14T03:01:00Z',
    nonce: 'n1', goal: 'open settings', capabilityScope: ['apps.open'], riskClass: 'A', signature: 'x'
  }, new Date('2026-09-14T04:00:00Z')))
})

test('device heartbeat is online only while fresh', () => {
  const now = new Date('2026-09-14T09:10:00Z')
  assert.equal(isDeviceOnline(null, now), false)
  assert.equal(isDeviceOnline('2026-09-14T09:09:55Z', now), true)
  assert.equal(isDeviceOnline('2026-09-14T09:09:20Z', now), false)
})

test('status queue pruning removes every expired command, not just the head', () => {
  const now = new Date('2026-09-14T09:10:00Z')
  const queue = [
    { commandId: 'live-1', expiresAt: '2026-09-14T09:11:00Z' },
    { commandId: 'dead', expiresAt: '2026-09-14T09:09:00Z' },
    { commandId: 'live-2', expiresAt: '2026-09-14T09:12:00Z' },
  ]
  assert.deepEqual(pruneExpiredCommands(queue, now).map(x => x.commandId), ['live-1', 'live-2'])
})

test('registry stores and returns the most recently active device', async () => {
  const values = new Map()
  const state = {
    storage: {
      get: async key => values.get(key),
      put: async (key, value) => values.set(key, value),
    },
    getWebSockets: () => [],
  }
  const session = new DeviceSession(state, {})
  const touch = await session.fetch(new Request('https://device.internal/registry/touch', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ deviceId: 'device-new' }),
  }))
  assert.equal(touch.status, 200)
  const latest = await session.fetch(new Request('https://device.internal/registry/latest'))
  assert.equal(latest.status, 200)
  assert.equal((await latest.json()).deviceId, 'device-new')
})

test('exact command result remains queryable after a later result overwrites lastResult', async () => {
  const token = 'device-token'
  const values = new Map([
    ['pairing', {
      paired: true,
      deviceId: 'device-1',
      deviceTokenHash: await sha256Base64(token),
    }],
  ])
  const state = {
    storage: {
      get: async key => values.get(key),
      put: async (key, value) => values.set(key, value),
    },
    getWebSockets: () => [],
  }
  const session = new DeviceSession(state, {})
  const headers = {
    authorization: `Bearer ${token}`,
    'content-type': 'application/json',
  }

  for (const result of [
    { commandId: 'command-1', status: 'FAILED', detail: 'POSTCONDITION_NOT_MET' },
    { commandId: 'command-2', status: 'COMPLETED', detail: '{"private":"must-not-leak"}' },
  ]) {
    const response = await session.fetch(new Request('https://device.internal/result', {
      method: 'POST', headers, body: JSON.stringify(result),
    }))
    assert.equal(response.status, 200)
  }

  const exact = await session.fetch(new Request('https://device.internal/command-result/command-1', {
    method: 'GET', headers: { authorization: `Bearer ${token}` },
  }))
  assert.equal(exact.status, 200)
  const body = await exact.json()
  assert.deepEqual(body, {
    commandId: 'command-1',
    status: 'FAILED',
    code: 'POSTCONDITION_NOT_MET',
    receivedAt: body.receivedAt,
  })
  assert.equal('detail' in body, false)
})
