import { importPrivateJwk, signCommand } from './crypto.js'

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...headers },
  })
}

async function sha256Base64(value) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  let binary = ''
  for (const b of new Uint8Array(digest)) binary += String.fromCharCode(b)
  return btoa(binary)
}

function bearer(request) {
  const h = request.headers.get('authorization') ?? ''
  return h.startsWith('Bearer ') ? h.slice(7) : null
}

export async function generateSigningMaterial() {
  const pair = await crypto.subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    true,
    ['sign', 'verify'],
  )
  const privateJwk = await crypto.subtle.exportKey('jwk', pair.privateKey)
  const publicJwk = await crypto.subtle.exportKey('jwk', pair.publicKey)
  return { privateJwk, publicJwk }
}

export async function signWithMaterial(command, material) {
  const privateKey = await importPrivateJwk(material.privateJwk)
  return signCommand(command, privateKey)
}

export function validateCommandForQueue(command, now = new Date()) {
  if (!command || command.schema !== 1) throw new Error('invalid schema')
  for (const key of ['commandId', 'deviceId', 'issuedAt', 'expiresAt', 'nonce', 'goal', 'riskClass', 'signature']) {
    if (!command[key]) throw new Error(`missing ${key}`)
  }
  if (!Array.isArray(command.capabilityScope)) throw new Error('invalid capabilityScope')
  const expiry = new Date(command.expiresAt)
  if (!Number.isFinite(expiry.getTime()) || expiry.getTime() <= now.getTime()) throw new Error('expired command')
  return command
}

export class DeviceSession {
  constructor(state, env) {
    this.state = state
    this.env = env
  }

  async fetch(request) {
    const url = new URL(request.url)
    if (url.pathname === '/pair/start' && request.method === 'POST') return this.pairStart(request)
    if (url.pathname === '/pair/complete' && request.method === 'POST') return this.pairComplete(request)
    if (url.pathname === '/status' && request.method === 'GET') return this.status(request)
    if (url.pathname === '/command' && request.method === 'POST') return this.enqueue(request)
    if (url.pathname === '/command-sign' && request.method === 'POST') return this.signAndEnqueue(request)
    if (url.pathname === '/next' && request.method === 'GET') return this.next(request)
    if (url.pathname === '/result' && request.method === 'POST') return this.result(request)
    if (url.pathname === '/socket' && request.headers.get('upgrade')?.toLowerCase() === 'websocket') return this.socket(request)
    return json({ error: 'not_found' }, 404)
  }

  async ensureSigningMaterial() {
    let material = await this.state.storage.get('signingMaterial')
    if (!material) {
      material = await generateSigningMaterial()
      await this.state.storage.put('signingMaterial', material)
    }
    return material
  }

  async pairStart(request) {
    const existing = await this.state.storage.get('pairing')
    if (existing?.paired) return json({ error: 'device_already_paired' }, 409)

    const body = await request.json()
    if (!body.deviceId || !body.devicePublicKey) return json({ error: 'deviceId_and_public_key_required' }, 400)
    const bytes = new Uint32Array(1)
    crypto.getRandomValues(bytes)
    const code = String(bytes[0] % 1000000).padStart(6, '0')
    const expiresAt = Date.now() + 5 * 60 * 1000
    await this.state.storage.put('pairing', {
      deviceId: body.deviceId,
      devicePublicKey: body.devicePublicKey,
      codeHash: await sha256Base64(code),
      expiresAt,
      paired: false,
    })
    return json({ deviceId: body.deviceId, code, expiresAt })
  }

  async pairComplete(request) {
    const body = await request.json()
    const pairing = await this.state.storage.get('pairing')
    if (!pairing || pairing.deviceId !== body.deviceId || Date.now() >= pairing.expiresAt) {
      return json({ error: 'pairing_expired_or_missing' }, 401)
    }
    if (await sha256Base64(String(body.code ?? '')) !== pairing.codeHash) return json({ error: 'invalid_pairing_code' }, 401)
    const raw = new Uint8Array(32)
    crypto.getRandomValues(raw)
    let token = ''
    for (const b of raw) token += b.toString(16).padStart(2, '0')
    pairing.paired = true
    pairing.codeHash = null
    pairing.deviceTokenHash = await sha256Base64(token)
    await this.state.storage.put('pairing', pairing)
    const material = await this.ensureSigningMaterial()
    return json({
      paired: true,
      deviceId: pairing.deviceId,
      deviceToken: token,
      gatewayPublicKeyJwk: material.publicJwk,
    })
  }

  async authorizedDevice(request) {
    const pairing = await this.state.storage.get('pairing')
    const token = bearer(request)
    if (!pairing?.paired || !token) return null
    return (await sha256Base64(token)) === pairing.deviceTokenHash ? pairing : null
  }

  async status(request) {
    const pairing = await this.state.storage.get('pairing')
    const queue = (await this.state.storage.get('queue')) ?? []
    const lastResult = await this.state.storage.get('lastResult')
    return json({ paired: Boolean(pairing?.paired), deviceId: pairing?.deviceId ?? null, queued: queue.length, lastResult: lastResult ?? null })
  }

  async enqueue(request) {
    return this.enqueueCommand(validateCommandForQueue(await request.json()))
  }

  async signAndEnqueue(request) {
    const command = await request.json()
    if (!command || command.schema !== 1 || !command.deviceId || !command.commandId) {
      return json({ error: 'invalid_unsigned_command' }, 400)
    }
    const pairing = await this.state.storage.get('pairing')
    if (!pairing?.paired || pairing.deviceId !== command.deviceId) return json({ error: 'device_not_paired' }, 409)
    const material = await this.ensureSigningMaterial()
    const signed = await signWithMaterial(command, material)
    return this.enqueueCommand(validateCommandForQueue(signed))
  }

  async enqueueCommand(command) {
    const pairing = await this.state.storage.get('pairing')
    if (!pairing?.paired || pairing.deviceId !== command.deviceId) return json({ error: 'device_not_paired' }, 409)
    const queue = (await this.state.storage.get('queue')) ?? []
    if (queue.some(x => x.nonce === command.nonce || x.commandId === command.commandId)) return json({ error: 'replay' }, 409)
    queue.push(command)
    while (queue.length > 50) queue.shift()
    await this.state.storage.put('queue', queue)
    for (const ws of this.state.getWebSockets()) {
      try { ws.send(JSON.stringify({ type: 'command_available', commandId: command.commandId })) } catch { }
    }
    return json({ queued: true, commandId: command.commandId }, 202)
  }

  async next(request) {
    const pairing = await this.authorizedDevice(request)
    if (!pairing) return json({ error: 'unauthorized_device' }, 401)
    const queue = (await this.state.storage.get('queue')) ?? []
    while (queue.length && new Date(queue[0].expiresAt).getTime() <= Date.now()) queue.shift()
    const command = queue.shift() ?? null
    await this.state.storage.put('queue', queue)
    return json({ command })
  }

  async result(request) {
    const pairing = await this.authorizedDevice(request)
    if (!pairing) return json({ error: 'unauthorized_device' }, 401)
    const body = await request.json()
    await this.state.storage.put('lastResult', { ...body, receivedAt: new Date().toISOString() })
    return json({ accepted: true })
  }

  async socket(request) {
    const pairing = await this.authorizedDevice(request)
    if (!pairing) return new Response('unauthorized', { status: 401 })
    const pair = new WebSocketPair()
    const client = pair[0]
    const server = pair[1]
    this.state.acceptWebSocket(server)
    server.send(JSON.stringify({ type: 'connected', deviceId: pairing.deviceId }))
    return new Response(null, { status: 101, webSocket: client })
  }

  async webSocketMessage(ws, message) {
    if (message === 'ping') ws.send('pong')
  }
}
