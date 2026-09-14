import { DeviceSession } from './device-session.js'
import { classifyGoal, validateRunGoal, TOOL_CONTRACT } from './tools.js'
import { verifyGitHubOidcToken } from './github-oidc.js'

export { DeviceSession }

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
})

function bearer(request) {
  const h = request.headers.get('authorization') ?? ''
  return h.startsWith('Bearer ') ? h.slice(7) : null
}

async function requireControl(request, env) {
  const token = bearer(request)
  if (!token) return { ok: false, response: json({ error: 'unauthorized' }, 401) }

  if (env.BRAIN_CONTROL_TOKEN && token === env.BRAIN_CONTROL_TOKEN) return { ok: true, mode: 'legacy-control-token' }

  try {
    const claims = await verifyGitHubOidcToken(token)
    return { ok: true, mode: 'github-oidc', claims }
  } catch (error) {
    return { ok: false, response: json({ error: 'unauthorized', detail: error.message }, 401) }
  }
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
        commandAuth: 'github-oidc',
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
      return proxyJson(sessionStub(env, body.deviceId), '/pair/complete', request)
    }

    const match = url.pathname.match(/^\/v1\/device\/([^/]+)\/(status|commands|next|result|socket)$/)
    if (match) {
      const deviceId = decodeURIComponent(match[1])
      const operation = match[2]
      const stub = sessionStub(env, deviceId)

      if (operation === 'status') {
        const auth = await requireControl(request, env)
        if (!auth.ok) return auth.response
        return stub.fetch(new Request('https://device.internal/status'))
      }

      if (operation === 'next') return proxyJson(stub, '/next', request)
      if (operation === 'result') return proxyJson(stub, '/result', request)
      if (operation === 'socket') return stub.fetch(request)

      if (operation === 'commands' && request.method === 'POST') {
        const auth = await requireControl(request, env)
        if (!auth.ok) return auth.response
        let input
        try { input = validateRunGoal(await request.json()) } catch (error) { return json({ error: error.message }, 400) }
        if (input.deviceId !== deviceId) return json({ error: 'device_mismatch' }, 400)
        const riskClass = classifyGoal(input.goal)
        if (riskClass === 'D') return json({ error: 'class_d_blocked' }, 403)
        if (riskClass === 'C') return json({ error: 'confirmation_required', riskClass }, 409)
        if (riskClass === 'B') return json({ error: 'class_b_not_enabled_in_v1_gateway', riskClass }, 409)

        const now = new Date()
        const command = {
          schema: 1,
          commandId: crypto.randomUUID(),
          deviceId,
          issuedAt: now.toISOString(),
          expiresAt: new Date(now.getTime() + 60_000).toISOString(),
          nonce: crypto.randomUUID(),
          goal: input.goal,
          capabilityScope: input.capabilityScope,
          riskClass,
        }
        return stub.fetch(new Request('https://device.internal/command-sign', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(command),
        }))
      }
    }

    return json({ error: 'not_found' }, 404)
  },
}
