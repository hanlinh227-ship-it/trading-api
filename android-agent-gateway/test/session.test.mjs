import test from 'node:test'
import assert from 'node:assert/strict'
import { isDeviceOnline, pruneExpiredCommands, validateCommandForQueue } from '../src/device-session.js'

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
