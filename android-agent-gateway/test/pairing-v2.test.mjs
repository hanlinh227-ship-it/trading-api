import test from 'node:test'
import assert from 'node:assert/strict'
import {
  deviceIdFromPublicKeySpki,
  pairingProofPayload,
  verifyPairingProof,
} from '../src/crypto.js'

test('device id is derived from the supplied SPKI public key', async () => {
  const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify'])
  const spki = new Uint8Array(await crypto.subtle.exportKey('spki', pair.publicKey))
  const publicKeyBase64 = Buffer.from(spki).toString('base64')
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', spki))
  const expected = [...digest.slice(0, 16)].map(x => x.toString(16).padStart(2, '0')).join('')
  assert.equal(await deviceIdFromPublicKeySpki(publicKeyBase64), expected)
})

test('pairing proof verifies possession of the device private key', async () => {
  const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify'])
  const spki = new Uint8Array(await crypto.subtle.exportKey('spki', pair.publicKey))
  const publicKeyBase64 = Buffer.from(spki).toString('base64')
  const deviceId = await deviceIdFromPublicKeySpki(publicKeyBase64)
  const challenge = 'challenge-123'
  const signature = new Uint8Array(await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    pair.privateKey,
    new TextEncoder().encode(pairingProofPayload(deviceId, challenge)),
  ))
  const signatureBase64 = Buffer.from(signature).toString('base64')

  assert.equal(await verifyPairingProof({ deviceId, challenge, publicKeyBase64, signatureBase64 }), true)
  assert.equal(await verifyPairingProof({ deviceId, challenge: 'tampered', publicKeyBase64, signatureBase64 }), false)
})
