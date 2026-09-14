import test from 'node:test'
import assert from 'node:assert/strict'
import { canonicalCommand, generateTestKeyPair, signCommand, verifyCommand } from '../src/crypto.js'

const baseCommand = {
  schema: 1,
  commandId: 'cmd-1',
  deviceId: 'device-1',
  issuedAt: '2026-09-14T04:00:00Z',
  expiresAt: '2026-09-14T04:01:00Z',
  nonce: 'nonce-1',
  goal: 'Open Settings',
  capabilityScope: ['apps.open'],
  riskClass: 'A'
}

test('signed command verifies and mutation fails', async () => {
  const keys = await generateTestKeyPair()
  const signed = await signCommand(baseCommand, keys.privateKey)
  assert.equal(await verifyCommand(signed, keys.publicKey), true)
  assert.equal(await verifyCommand({...signed, goal: 'mutated'}, keys.publicKey), false)
  assert.match(signed.signature, /^[A-Za-z0-9+/]+=*$/)
})

test('schema-2 canonical command matches Android deterministic representation', () => {
  const command = {
    schema: 2,
    commandId: 'cmd-2',
    deviceId: 'device-1',
    issuedAt: '2026-09-14T03:59:59Z',
    expiresAt: '2026-09-14T04:01:00Z',
    nonce: 'nonce-2',
    taskId: 'task-7',
    action: { type: 'tap_point', x: 120, y: 340 },
    capabilityScope: ['ui.navigate'],
    riskClass: 'A',
  }
  assert.equal(canonicalCommand(command), [
    '2', 'cmd-2', 'device-1', '2026-09-14T03:59:59Z', '2026-09-14T04:01:00Z',
    'nonce-2', 'task-7', '{"type":"tap_point","x":120,"y":340}', 'ui.navigate', 'A',
  ].join('\n'))
})

test('schema-2 signed action verifies and action mutation fails', async () => {
  const keys = await generateTestKeyPair()
  const command = {
    schema: 2,
    commandId: 'cmd-2', deviceId: 'device-1',
    issuedAt: '2026-09-14T04:00:00Z', expiresAt: '2026-09-14T04:01:00Z', nonce: 'nonce-2',
    taskId: 'task-1', action: { type: 'global_back' }, capabilityScope: ['ui.navigate'], riskClass: 'A',
  }
  const signed = await signCommand(command, keys.privateKey)
  assert.equal(await verifyCommand(signed, keys.publicKey), true)
  assert.equal(await verifyCommand({ ...signed, action: { type: 'global_home' } }, keys.publicKey), false)
})
