import test from 'node:test'
import assert from 'node:assert/strict'
import { generateTestKeyPair, signCommand, verifyCommand } from '../src/crypto.js'

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
