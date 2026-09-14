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
