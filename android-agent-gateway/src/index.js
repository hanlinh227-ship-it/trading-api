import { DeviceSession } from './device-session.js'
import { importPrivateJwk, publicJwkFromPrivate, signCommand } from './crypto.js'
import { classifyGoal, validateRunGoal, TOOL_CONTRACT } from './tools.js'

export { DeviceSession }

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
})

function bearer(request) {
  const h = request.headers.get('authorization') ?? ''
  return h.startsWith('Bearer ') ? h.slice(7) : null
}

function requireControl(request, env) {
  if (!env.BRAIN_CONTROL_TOKEN) return { ok: false, response: json({ error: 'control_token_not_configured' }, 503) }
  if (bearer(request) !== env.BRAIN_CONTROL_TOKEN) return { ok: false, response: json({ error: 'unauthorized' }, 401) }
  return { ok: true }
}

function sessionStub(env, deviceId) {
  const id = env.DEVICE_SESSIONS.idFromName(`device:${deviceId}`)
  return env.DEVICE_SESSIONS.get(id)
}

async function proxyJson(stub, path, request) {
  const body = request.method === 'GET' ? undefined : await request.text()
  return stub.fetch(new Request(`https://device.internal${path}`, {
    method: request.method,
    headers: request.headers,
    body,
  }))
}

async function signingPrivateKey(env) {
  if (!env.GATEWAY_SIGNING_PRIVATE_JWK) throw new Error('gateway_signing_key_not_configured')
  return importPrivateJwk(env.GATEWAY_SIGNING_PRIVATE_JWK)
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)

    if (url.pathname === '/health') {
      return json({
        ok: true,
        schema: 1,
        service: 'android-brain-agent-gateway',
        sourceSha: env.DEPLOYMENT_SOURCE_SHA ?? 'development',
        tradingAuthority: false,
        rawShell: false,
        tools: TOOL_CONTRACT,
      })
    }

    if (url.pathname === '/v1/pair/start' && request.method === 'POST') {
      const body = await request.clone().json().catch(() => null)
      if (!body?.deviceId) return json({ error: 'deviceId_required' }, 400)
      return proxyJson(sessionStub(env, body.deviceId), '/pair/start', request)
    }

    if (url.pathname === '/v1/pair/complete' && request.method === 'POST') {
      const body = await request.clone().json().catch(() => null)
      if (!body?.deviceId) return json({ error: 'deviceId_required' }, 400)
      let privateKey
      try { privateKey = await signingPrivateKey(env) } catch (error) { return json({ error: error.message }, 503) }
      const response = await proxyJson(sessionStub(env, body.deviceId), '/pair/complete', request)
      if (!response.ok) return response
      const paired = await response.json()
      return json({ ...paired, gatewayPublicKeyJwk: await publicJwkFromPrivate(privateKey) })
    }

    const match = url.pathname.match(/^\/v1\/device\/([^/]+)\/(status|commands|next|result|socket)$/)
    if (match) {
      const deviceId = decodeURIComponent(match[1])
      const operation = match[2]
      const stub = sessionStub(env, deviceId)

      if (operation === 'status') {
        const auth = requireControl(request, env)
        if (!auth.ok) return auth.response
        return stub.fetch(new Request('https://device.internal/status'))
      }

      if (operation === 'next') return proxyJson(stub, '/next', request)
      if (operation === 'result') return proxyJson(stub, '/result', request)
      if (operation === 'socket') return stub.fetch(request)

      if (operation === 'commands' && request.method === 'POST') {
        const auth = requireControl(request, env)
        if (!auth.ok) return auth.response
        let input
        try { input = validateRunGoal(await request.json()) } catch (error) { return json({ error: error.message }, 400) }
        if (input.deviceId !== deviceId) return json({ error: 'device_mismatch' }, 400)
        const riskClass = classifyGoal(input.goal)
        if (riskClass === 'D') return json({ error: 'class_d_blocked' }, 403)
        if (riskClass === 'C') return json({ error: 'confirmation_required', riskClass }, 409)
        if (riskClass === 'B') return json({ error: 'class_b_not_enabled_in_v1_gateway', riskClass }, 409)

        let privateKey
        try { privateKey = await signingPrivateKey(env) } catch (error) { return json({ error: error.message }, 503) }
        const now = new Date()
        const command = await signCommand({
          schema: 1,
          commandId: crypto.randomUUID(),
          deviceId,
          issuedAt: now.toISOString(),
          expiresAt: new Date(now.getTime() + 60_000).toISOString(),
          nonce: crypto.randomUUID(),
          goal: input.goal,
          capabilityScope: input.capabilityScope,
          riskClass,
        }, privateKey)
        return stub.fetch(new Request('https://device.internal/command', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(command),
        }))
      }
    }

    return json({ error: 'not_found' }, 404)
  },
}
