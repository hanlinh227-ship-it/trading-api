import test from 'node:test'
import assert from 'node:assert/strict'
import { generateSigningMaterial, signWithMaterial } from '../src/device-session.js'
import { verifyCommand } from '../src/crypto.js'

test('device session signing material signs without environment secret', async () => {
  const material = await generateSigningMaterial()
  const publicKey = await crypto.subtle.importKey(
    'jwk', material.publicJwk,
    { name: 'ECDSA', namedCurve: 'P-256' }, true, ['verify']
  )
  const signed = await signWithMaterial({
    schema: 1,
    commandId: 'c1',
    deviceId: 'd1',
    issuedAt: new Date(Date.now() - 1000).toISOString(),
    expiresAt: new Date(Date.now() + 60000).toISOString(),
    nonce: 'n1',
    goal: 'Open Settings',
    capabilityScope: ['apps.open'],
    riskClass: 'A',
  }, material)
  assert.ok(signed.signature)
  assert.equal(await verifyCommand(signed, publicKey), true)
})
