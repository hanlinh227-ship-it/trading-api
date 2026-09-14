import { validateTypedAction } from './action-schema.js'
import { importPrivateJwk, signCommand, verifyPairingProof } from './crypto.js'
import { planNextStep } from './planner.js'
import { clampTaskStep, createTaskState, publicTaskState, recordTaskProgress } from './task-policy.js'

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

function terminalStatus(status) {
  return ['COMPLETED', 'FAILED', 'CANCELLED'].includes(status)
}

const RECOVERABLE_RESULT_CODES = new Set([
  'ACTION_DISPATCH_FAILED',
  'POSTCONDITION_NOT_MET',
])

function safeResultCode(result) {
  const code = result?.code ?? result?.detail ?? null
  if (code == null) return null
  return String(code).replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 96)
}

function observationFingerprint(observation) {
  return typeof observation?.fingerprint === 'string' ? observation.fingerprint.slice(0, 192) : null
}

function observationText(observation) {
  return (Array.isArray(observation?.nodes) ? observation.nodes : [])
    .flatMap(node => [node?.text, node?.contentDescription])
    .filter(value => typeof value === 'string')
    .join('\n')
    .slice(0, 16_384)
}

function expectedSatisfied(expected, observation, previousFingerprint) {
  if (!expected) return true
  switch (expected.type) {
    case 'observation_returned': return Boolean(observation && typeof observation === 'object')
    case 'observation_changed': {
      const next = observationFingerprint(observation)
      return Boolean(next && previousFingerprint && next !== previousFingerprint)
    }
    case 'foreground_package': return observation?.packageName === expected.packageName
    case 'node_visible': return (observation?.nodes ?? []).some(node => node?.nodeId === expected.nodeId)
    case 'node_missing': return !(observation?.nodes ?? []).some(node => node?.nodeId === expected.nodeId)
    case 'text_present': return expected.text ? observationText(observation).includes(expected.text) : false
    case 'text_missing': return expected.text ? !observationText(observation).includes(expected.text) : false
    case 'task_complete': return true
    default: return false
  }
}

function appendSafeHistory(task, entry) {
  const history = [...(Array.isArray(task.history) ? task.history : []), entry]
  return history.slice(-6)
}

export function isDeviceOnline(lastSeenAt, now = new Date(), maxAgeMs = 15_000) {
  if (!lastSeenAt) return false
  const seen = new Date(lastSeenAt).getTime()
  return Number.isFinite(seen) && now.getTime() - seen <= maxAgeMs && seen <= now.getTime() + 5_000
}

export function pruneExpiredCommands(queue, now = new Date()) {
  const nowMs = now.getTime()
  return (Array.isArray(queue) ? queue : []).filter(command => {
    const expiry = new Date(command?.expiresAt).getTime()
    return Number.isFinite(expiry) && expiry > nowMs
  })
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
  if (!command || (command.schema !== 1 && command.schema !== 2)) throw new Error('invalid schema')
  for (const key of ['commandId', 'deviceId', 'issuedAt', 'expiresAt', 'nonce', 'riskClass', 'signature']) {
    if (!command[key]) throw new Error(`missing ${key}`)
  }
  if (!Array.isArray(command.capabilityScope)) throw new Error('invalid capabilityScope')
  if (command.schema === 1 && !command.goal) throw new Error('missing goal')
  if (command.schema === 2) {
    if (!command.taskId) throw new Error('missing taskId')
    command.action = validateTypedAction(command.action)
  }
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
    if (url.pathname === '/registry/touch' && request.method === 'POST') return this.registryTouch(request)
    if (url.pathname === '/registry/latest' && request.method === 'GET') return this.registryLatest()
    if (url.pathname === '/pair/start' && request.method === 'POST') return this.pairStart(request)
    if (url.pathname === '/pair/complete' && request.method === 'POST') return this.pairComplete(request)
    if (url.pathname === '/status' && request.method === 'GET') return this.status(request)
    if (url.pathname === '/command' && request.method === 'POST') return this.enqueue(request)
    if (url.pathname === '/command-sign' && request.method === 'POST') return this.signAndEnqueue(request)
    if (url.pathname === '/task' && request.method === 'POST') return this.createTask(request)
    if (url.pathname.startsWith('/task/') && request.method === 'GET') return this.getTask(url.pathname.slice('/task/'.length))
    if (url.pathname === '/task-step' && request.method === 'POST') return this.taskStep(request)
    if (url.pathname === '/next' && request.method === 'GET') return this.next(request)
    if (url.pathname === '/result' && request.method === 'POST') return this.result(request)
    if (url.pathname === '/socket' && request.headers.get('upgrade')?.toLowerCase() === 'websocket') return this.socket(request)
    return json({ error: 'not_found' }, 404)
  }

  async registryTouch(request) {
    const body = await request.json().catch(() => null)
    if (!body?.deviceId || typeof body.deviceId !== 'string') return json({ error: 'deviceId_required' }, 400)
    const latest = { deviceId: body.deviceId, lastSeenAt: new Date().toISOString() }
    await this.state.storage.put('latestDevice', latest)
    return json(latest)
  }

  async registryLatest() {
    const latest = await this.state.storage.get('latestDevice')
    return json(latest ?? { deviceId: null, lastSeenAt: null })
  }

  async ensureSigningMaterial() {
    let material = await this.state.storage.get('signingMaterial')
    if (!material) {
      material = await generateSigningMaterial()
      await this.state.storage.put('signingMaterial', material)
    }
    return material
  }

  async markDeviceSeen() {
    const lastSeenAt = new Date().toISOString()
    await this.state.storage.put('lastSeenAt', lastSeenAt)
    return lastSeenAt
  }

  async pairStart(request) {
    const body = await request.json()
    if (!body.deviceId || !body.devicePublicKey) return json({ error: 'deviceId_and_public_key_required' }, 400)

    const existing = await this.state.storage.get('pairing')
    if (existing?.paired && existing.devicePublicKey !== body.devicePublicKey) {
      return json({ error: 'device_already_paired_with_different_key' }, 409)
    }

    const challenge = `${crypto.randomUUID()}-${crypto.randomUUID()}`
    const expiresAt = Date.now() + 5 * 60 * 1000
    const pairing = {
      ...(existing ?? {}),
      deviceId: body.deviceId,
      devicePublicKey: body.devicePublicKey,
      challengeHash: await sha256Base64(challenge),
      expiresAt,
      paired: Boolean(existing?.paired),
    }
    await this.state.storage.put('pairing', pairing)
    return json({ deviceId: body.deviceId, challenge, expiresAt, recovery: Boolean(existing?.paired) })
  }

  async pairComplete(request) {
    const body = await request.json()
    const pairing = await this.state.storage.get('pairing')
    if (!pairing || pairing.deviceId !== body.deviceId || Date.now() >= pairing.expiresAt) {
      return json({ error: 'pairing_expired_or_missing' }, 401)
    }
    if (!body.challenge || !body.signature) return json({ error: 'pairing_proof_required' }, 400)
    if (await sha256Base64(String(body.challenge)) !== pairing.challengeHash) {
      return json({ error: 'invalid_pairing_challenge' }, 401)
    }
    const proofOk = await verifyPairingProof({
      deviceId: pairing.deviceId,
      challenge: body.challenge,
      publicKeyBase64: pairing.devicePublicKey,
      signatureBase64: body.signature,
    })
    if (!proofOk) return json({ error: 'invalid_pairing_proof' }, 401)

    const raw = new Uint8Array(32)
    crypto.getRandomValues(raw)
    let token = ''
    for (const b of raw) token += b.toString(16).padStart(2, '0')
    pairing.paired = true
    pairing.challengeHash = null
    pairing.deviceTokenHash = await sha256Base64(token)
    await this.state.storage.put('pairing', pairing)
    const material = await this.ensureSigningMaterial()
    return json({
      paired: true,
      recovered: Boolean(body.recovery),
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
    const rawQueue = (await this.state.storage.get('queue')) ?? []
    const queue = pruneExpiredCommands(rawQueue)
    if (queue.length !== rawQueue.length) await this.state.storage.put('queue', queue)
    const lastResult = await this.state.storage.get('lastResult')
    const lastSeenAt = await this.state.storage.get('lastSeenAt')
    return json({
      paired: Boolean(pairing?.paired),
      deviceId: pairing?.deviceId ?? null,
      online: isDeviceOnline(lastSeenAt),
      lastSeenAt: lastSeenAt ?? null,
      queued: queue.length,
      lastResult: lastResult ?? null,
    })
  }

  async createTask(request) {
    let task
    try {
      task = createTaskState(await request.json())
    } catch (error) {
      return json({ error: error.message }, 400)
    }
    const key = `task:${task.taskId}`
    if (await this.state.storage.get(key)) return json({ error: 'task_exists' }, 409)
    await this.state.storage.put(key, {
      ...task,
      history: [],
      pendingExpected: null,
      pendingActionType: null,
      pendingCommandId: null,
      lastProcessedCommandId: null,
    })
    return json(publicTaskState(task), 201)
  }

  async getTask(taskId) {
    const task = await this.state.storage.get(`task:${decodeURIComponent(taskId)}`)
    if (!task) return json({ error: 'task_not_found' }, 404)
    return json(publicTaskState(task))
  }

  async taskStep(request) {
    const pairing = await this.authorizedDevice(request)
    if (!pairing) return json({ error: 'unauthorized_device' }, 401)
    await this.markDeviceSeen()

    const body = await request.json().catch(() => null)
    if (!body?.taskId || typeof body.taskId !== 'string') return json({ error: 'task_id_required' }, 400)
    if (!body.observation || typeof body.observation !== 'object') return json({ error: 'observation_required' }, 400)
    const key = `task:${body.taskId}`
    let task = await this.state.storage.get(key)
    if (!task) return json({ error: 'task_not_found' }, 404)

    const currentFingerprint = observationFingerprint(body.observation)
    const previousResult = body.previousResult && typeof body.previousResult === 'object' ? body.previousResult : null
    const previousCommandId = typeof previousResult?.commandId === 'string' ? previousResult.commandId : null

    if (previousCommandId && previousCommandId === task.lastProcessedCommandId) {
      return json({ ...publicTaskState(task), duplicate: true })
    }
    if (terminalStatus(task.status)) return json({ error: 'task_terminal', status: task.status }, 409)
    if (previousResult && task.pendingCommandId && previousCommandId !== task.pendingCommandId) {
      return json({ error: 'stale_or_unknown_result' }, 409)
    }

    try {
      if (previousResult) {
        task = recordTaskProgress(task, { kind: 'step', status: 'VERIFYING' })
        const resultStatus = String(previousResult.status ?? '').toUpperCase()
        const resultCode = safeResultCode(previousResult)
        const verificationOk = resultStatus === 'COMPLETED' && expectedSatisfied(task.pendingExpected, body.observation, task.lastFingerprint)
        const recoverableFailure = resultStatus === 'FAILED' && RECOVERABLE_RESULT_CODES.has(resultCode)
        const fatalFailure = resultStatus === 'NEEDS_CONFIRMATION' || (resultStatus === 'FAILED' && !recoverableFailure)
        const noOp = resultStatus === 'COMPLETED' && task.pendingExpected?.type === 'observation_changed' && !verificationOk

        task.history = appendSafeHistory(task, {
          actionType: task.pendingActionType ?? null,
          result: resultStatus === 'FAILED' || resultStatus === 'NEEDS_CONFIRMATION'
            ? (resultCode ?? resultStatus)
            : (verificationOk ? 'VERIFIED' : (noOp ? 'NO_OP' : resultStatus)),
          fingerprint: currentFingerprint,
        })
        task = {
          ...task,
          lastProcessedCommandId: previousCommandId ?? task.pendingCommandId ?? null,
          pendingCommandId: null,
        }

        if (fatalFailure) {
          const code = resultCode ?? (resultStatus === 'NEEDS_CONFIRMATION' ? 'CLASS_C_CONFIRMATION_REQUIRED' : 'FAILED')
          task = {
            ...task,
            status: 'FAILED',
            failureCode: code,
            lastFingerprint: currentFingerprint,
            pendingExpected: null,
            pendingActionType: null,
            updatedAt: new Date().toISOString(),
          }
          await this.state.storage.put(key, task)
          return json({ ...publicTaskState(task), error: code })
        }

        if (recoverableFailure || noOp || !verificationOk) {
          task = recordTaskProgress(task, { kind: 'recovery', fingerprint: currentFingerprint, status: 'RECOVERING' })
        } else {
          task = { ...task, recoveryCount: 0, lastFingerprint: currentFingerprint, status: 'PLANNING', updatedAt: new Date().toISOString() }
        }
      } else {
        task = { ...task, lastFingerprint: currentFingerprint, status: 'PLANNING', updatedAt: new Date().toISOString() }
      }
    } catch (error) {
      const code = error.message === 'max_steps_exceeded' ? 'STEP_LIMIT' : error.message === 'max_recoveries_exceeded' ? 'RECOVERY_LIMIT' : 'TASK_PROGRESS_ERROR'
      task = {
        ...task,
        status: 'FAILED',
        failureCode: code,
        pendingCommandId: null,
        pendingExpected: null,
        pendingActionType: null,
        updatedAt: new Date().toISOString(),
      }
      await this.state.storage.put(key, task)
      return json({ ...publicTaskState(task), error: code }, 409)
    }

    let planned
    try {
      planned = await planNextStep({
        env: this.env,
        task,
        observation: body.observation,
        imageDataUrl: typeof body.imageDataUrl === 'string' ? body.imageDataUrl : null,
        history: task.history,
      })
    } catch {
      task = {
        ...task,
        status: 'FAILED',
        failureCode: 'PLANNER_FAILED',
        pendingCommandId: null,
        pendingExpected: null,
        pendingActionType: null,
        updatedAt: new Date().toISOString(),
      }
      await this.state.storage.put(key, task)
      return json({ ...publicTaskState(task), error: 'PLANNER_FAILED' }, 500)
    }

    let step
    try {
      step = clampTaskStep({ task, action: planned.action, observation: body.observation })
    } catch (error) {
      task = {
        ...task,
        status: 'FAILED',
        failureCode: error.message,
        pendingCommandId: null,
        pendingExpected: null,
        pendingActionType: null,
        updatedAt: new Date().toISOString(),
      }
      await this.state.storage.put(key, task)
      return json({ ...publicTaskState(task), error: error.message }, 403)
    }

    if (planned.expected?.type === 'task_complete') {
      task = {
        ...task,
        status: 'COMPLETED',
        pendingExpected: null,
        pendingActionType: null,
        pendingCommandId: null,
        lastFingerprint: currentFingerprint,
        updatedAt: new Date().toISOString(),
      }
      await this.state.storage.put(key, task)
      return json({ ...publicTaskState(task), plannerMode: planned.mode })
    }

    const now = new Date()
    const commandScope = [step.capability]
    if (task.capabilityScope.includes('contacts.read')) commandScope.push('contacts.read')
    if (step.riskClass === 'C') commandScope.push('ui.destructive.confirmed')
    const command = {
      schema: 2,
      commandId: crypto.randomUUID(),
      deviceId: pairing.deviceId,
      issuedAt: now.toISOString(),
      expiresAt: new Date(now.getTime() + 60_000).toISOString(),
      nonce: crypto.randomUUID(),
      taskId: task.taskId,
      action: step.action,
      capabilityScope: [...new Set(commandScope)],
      riskClass: step.riskClass,
    }
    const material = await this.ensureSigningMaterial()
    const signed = validateCommandForQueue(await signWithMaterial(command, material))
    const queued = await this.enqueueCommand(signed)
    if (!queued.ok) return queued

    task = {
      ...task,
      status: 'ACTING',
      lastFingerprint: currentFingerprint,
      pendingExpected: planned.expected,
      pendingActionType: step.action.type,
      pendingCommandId: command.commandId,
      updatedAt: new Date().toISOString(),
    }
    await this.state.storage.put(key, task)
    return json({
      ...publicTaskState(task),
      plannerMode: planned.mode,
      commandId: command.commandId,
    }, 202)
  }

  async enqueue(request) {
    return this.enqueueCommand(validateCommandForQueue(await request.json()))
  }

  async signAndEnqueue(request) {
    const command = await request.json()
    if (!command || (command.schema !== 1 && command.schema !== 2) || !command.deviceId || !command.commandId) {
      return json({ error: 'invalid_unsigned_command' }, 400)
    }
    if (command.schema === 1 && !command.goal) return json({ error: 'invalid_unsigned_command' }, 400)
    if (command.schema === 2) {
      if (!command.taskId || !command.action) return json({ error: 'invalid_unsigned_command' }, 400)
      try { command.action = validateTypedAction(command.action) } catch (error) { return json({ error: error.message }, 400) }
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
    const queue = pruneExpiredCommands((await this.state.storage.get('queue')) ?? [])
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
    await this.markDeviceSeen()
    const queue = pruneExpiredCommands((await this.state.storage.get('queue')) ?? [])
    const command = queue.shift() ?? null
    await this.state.storage.put('queue', queue)
    return json({ command })
  }

  async result(request) {
    const pairing = await this.authorizedDevice(request)
    if (!pairing) return json({ error: 'unauthorized_device' }, 401)
    await this.markDeviceSeen()
    const body = await request.json()
    const safe = {
      commandId: typeof body?.commandId === 'string' ? body.commandId.slice(0, 128) : null,
      status: typeof body?.status === 'string' ? body.status.slice(0, 64) : null,
      detail: typeof body?.detail === 'string' ? body.detail.slice(0, 512) : null,
      receivedAt: new Date().toISOString(),
    }
    await this.state.storage.put('lastResult', safe)
    return json({ accepted: true })
  }

  async socket(request) {
    const pairing = await this.authorizedDevice(request)
    if (!pairing) return new Response('unauthorized', { status: 401 })
    await this.markDeviceSeen()
    const pair = new WebSocketPair()
    const client = pair[0]
    const server = pair[1]
    this.state.acceptWebSocket(server)
    server.send(JSON.stringify({ type: 'connected', deviceId: pairing.deviceId }))
    return new Response(null, { status: 101, webSocket: client })
  }

  async webSocketMessage(ws, message) {
    if (message === 'ping') {
      await this.markDeviceSeen()
      ws.send('pong')
    }
  }
}
