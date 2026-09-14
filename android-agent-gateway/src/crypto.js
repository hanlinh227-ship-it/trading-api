import { validateTypedAction } from './action-schema.js'

const enc = new TextEncoder()

function bytesToBase64(bytes) {
  let binary = ''
  for (const b of new Uint8Array(bytes)) binary += String.fromCharCode(b)
  return btoa(binary)
}

function base64ToBytes(value) {
  const binary = atob(value)
  const out = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i)
  return out
}

export function canonicalCommand(command) {
  const scope = [...(command.capabilityScope ?? [])].sort().join(',')
  if (command.schema === 1) {
    return [
      String(command.schema),
      command.commandId,
      command.deviceId,
      command.issuedAt,
      command.expiresAt,
      command.nonce,
      command.goal,
      scope,
      command.riskClass,
    ].join('\n')
  }
  if (command.schema === 2) {
    const actionJson = JSON.stringify(validateTypedAction(command.action))
    return [
      String(command.schema),
      command.commandId,
      command.deviceId,
      command.issuedAt,
      command.expiresAt,
      command.nonce,
      command.taskId,
      actionJson,
      scope,
      command.riskClass,
    ].join('\n')
  }
  throw new Error('invalid schema')
}

export function pairingProofPayload(deviceId, challenge) {
  return `android-brain-pair-v2\n${deviceId}\n${challenge}`
}

export async function deviceIdFromPublicKeySpki(publicKeyBase64) {
  const spki = base64ToBytes(publicKeyBase64)
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', spki))
  return [...digest.slice(0, 16)].map(x => x.toString(16).padStart(2, '0')).join('')
}

export async function verifyPairingProof({ deviceId, challenge, publicKeyBase64, signatureBase64 }) {
  try {
    if (!deviceId || !challenge || !publicKeyBase64 || !signatureBase64) return false
    if (await deviceIdFromPublicKeySpki(publicKeyBase64) !== deviceId) return false
    const publicKey = await crypto.subtle.importKey(
      'spki',
      base64ToBytes(publicKeyBase64),
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['verify'],
    )
    return await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' },
      publicKey,
      base64ToBytes(signatureBase64),
      enc.encode(pairingProofPayload(deviceId, challenge)),
    )
  } catch {
    return false
  }
}

export async function generateTestKeyPair() {
  return crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify'])
}

export async function signCommand(command, privateKey) {
  const unsigned = { ...command }
  delete unsigned.signature
  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    privateKey,
    enc.encode(canonicalCommand(unsigned)),
  )
  return { ...unsigned, signature: bytesToBase64(signature) }
}

export async function verifyCommand(command, publicKey) {
  try {
    const unsigned = { ...command }
    const signature = unsigned.signature
    delete unsigned.signature
    if (!signature) return false
    return await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' },
      publicKey,
      base64ToBytes(signature),
      enc.encode(canonicalCommand(unsigned)),
    )
  } catch {
    return false
  }
}

export async function importPrivateJwk(jwk) {
  return crypto.subtle.importKey(
    'jwk',
    typeof jwk === 'string' ? JSON.parse(jwk) : jwk,
    { name: 'ECDSA', namedCurve: 'P-256' },
    true,
    ['sign'],
  )
}

export async function publicJwkFromPrivate(privateKey) {
  const jwk = await crypto.subtle.exportKey('jwk', privateKey)
  const { d, key_ops, ...publicJwk } = jwk
  return { ...publicJwk, key_ops: ['verify'] }
}
