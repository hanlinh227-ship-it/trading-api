import { DeviceSession } from './device-session.js'
import { classifyGoal, validateRunGoal, TOOL_CONTRACT } from './tools.js'
import { verifyGitHubOidcToken } from './github-oidc.js'

export { DeviceSession }

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
})

const RISK_ORDER = Object.freeze({ A: 0, B: 1, C: 2, D: 3 })

export function healthPayload(env = {}) {
  return {
    ok: true,
    schema: 1,
    taskSchema: 2,
    service: 'android-brain-agent-gateway',
    sourceSha: env.DEPLOYMENT_SOURCE_SHA ?? 'development',
    tradingAuthority: false,
    rawShell: false,
    commandAuth: 'github-oidc',
    plannerMode: env.AI ? 'workers-ai-with-deterministic-fallback' : 'deterministic-fallback-only',
    capabilities: {
      typedActions: true,
      ephemeralScreenshots: true,
      localContacts: true,
      boundedTaskSessions: true,
      securityBypass: false,
      financialMutation: false,
    },
    tools: TOOL_CONTRACT,
  }
}

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

function registryStub(env) {
  return sessionStub(env, '__latest_device_registry__')
}

async function touchLatestDevice(env, deviceId) {
  await registryStub(env).fetch(new Request('https://device.internal/registry/touch', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ deviceId }),
  }))
}

async function proxyJson(stub, path, request) {
  const body = request.method === 'GET' ? undefined : await request.text()
  return stub.fetch(new Request(`https://device.internal${path}`, {
    method: request.method,
    headers: request.headers,
    body,
  }))
}

function normalizedTaskInput(body, authMode) {
  if (!body || typeof body !== 'object') throw new Error('input_required')
  if (typeof body.goal !== 'string' || !body.goal.trim()) throw new Error('goal_required')
  const goalRisk = classifyGoal(body.goal)
  if (goalRisk === 'D') throw new Error('class_d_blocked')
  const riskCeiling = body.riskCeiling ?? goalRisk
  if (!(riskCeiling in RISK_ORDER) || riskCeiling === 'D') throw new Error('invalid_risk_ceiling')
  if (RISK_ORDER[goalRisk] > RISK_ORDER[riskCeiling]) throw new Error('goal_exceeds_risk_ceiling')
  if (goalRisk === 'C' && body.confirmedRiskClassC !== true) throw new Error('confirmation_required')
  if (goalRisk === 'C' && authMode !== 'github-oidc') throw new Error('class_c_requires_github_oidc')
  const taskId = typeof body.taskId === 'string' && body.taskId.trim() ? body.taskId.trim() : crypto.randomUUID()
  const scope = Array.isArray(body.capabilityScope) && body.capabilityScope.length
    ? [...new Set(body.capabilityScope.map(String))]
    : ['apps.open', 'ui.navigate']
  return {
    taskId,
    goal: body.goal.trim(),
    capabilityScope: scope,
    riskClass: riskCeiling,
    confirmedRiskClassC: goalRisk === 'C' && body.confirmedRiskClassC === true,
    confirmedTaskId: goalRisk === 'C' && body.confirmedRiskClassC === true ? taskId : null,
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)

    if (url.pathname === '/health') return json(healthPayload(env))

    if (url.pathname === '/v1/device/latest' && request.method === 'GET') {
      const auth = await requireControl(request, env)
      if (!auth.ok) return auth.response
      return registryStub(env).fetch(new Request('https://device.internal/registry/latest'))
    }

    if (url.pathname === '/v1/pair/start' && request.method === 'POST') {
      const body = await request.clone().json().catch(() => null)
      if (!body?.deviceId) return json({ error: 'deviceId_required' }, 400)
      return proxyJson(sessionStub(env, body.deviceId), '/pair/start', request)
    }

    if (url.pathname === '/v1/pair/complete' && request.method === 'POST') {
      const body = await request.clone().json().catch(() => null)
      if (!body?.deviceId) return json({ error: 'deviceId_required' }, 400)
      const response = await proxyJson(sessionStub(env, body.deviceId), '/pair/complete', request)
      if (response.ok) await touchLatestDevice(env, body.deviceId)
      return response
    }

    const taskMatch = url.pathname.match(/^\/v1\/device\/([^/]+)\/tasks(?:\/([^/]+))?$/)
    if (taskMatch) {
      const deviceId = decodeURIComponent(taskMatch[1])
      const taskId = taskMatch[2] ? decodeURIComponent(taskMatch[2]) : null
      const auth = await requireControl(request, env)
      if (!auth.ok) return auth.response
      const stub = sessionStub(env, deviceId)

      if (request.method === 'POST' && taskId == null) {
        const body = await request.json().catch(() => null)
        let task
        try { task = normalizedTaskInput(body, auth.mode) } catch (error) {
          const status = error.message.includes('class_d') ? 403 : error.message.includes('confirmation') ? 409 : 400
          return json({ error: error.message }, status)
        }
        return stub.fetch(new Request('https://device.internal/task', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(task),
        }))
      }

      if (request.method === 'GET' && taskId) {
        return stub.fetch(new Request(`https://device.internal/task/${encodeURIComponent(taskId)}`))
      }

      return json({ error: 'method_not_allowed' }, 405)
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

      if (operation === 'next') {
        const response = await proxyJson(stub, '/next', request)
        if (response.ok) await touchLatestDevice(env, deviceId)
        return response
      }

      if (operation === 'result') {
        const response = await proxyJson(stub, '/result', request)
        if (response.ok) await touchLatestDevice(env, deviceId)
        return response
      }

      if (operation === 'socket') return stub.fetch(request)

      if (operation === 'commands' && request.method === 'POST') {
        const auth = await requireControl(request, env)
        if (!auth.ok) return auth.response
        let input
        try { input = validateRunGoal(await request.json()) } catch (error) { return json({ error: error.message }, 400) }
        if (input.deviceId !== deviceId) return json({ error: 'device_mismatch' }, 400)
        const riskClass = classifyGoal(input.goal)
        if (riskClass === 'D') return json({ error: 'class_d_blocked' }, 403)
        if (riskClass === 'C' && !input.confirmedRiskClassC) {
          return json({ error: 'confirmation_required', riskClass }, 409)
        }
        if (riskClass === 'C' && auth.mode !== 'github-oidc') {
          return json({ error: 'class_c_requires_github_oidc', riskClass }, 403)
        }
        if (riskClass === 'B') return json({ error: 'class_b_not_enabled_in_v1_gateway', riskClass }, 409)

        const capabilityScope = [...new Set(input.capabilityScope)]
        if (riskClass === 'C') capabilityScope.push('ui.destructive.confirmed')

        const now = new Date()
        const command = {
          schema: 1,
          commandId: crypto.randomUUID(),
          deviceId,
          issuedAt: now.toISOString(),
          expiresAt: new Date(now.getTime() + 60_000).toISOString(),
          nonce: crypto.randomUUID(),
          goal: input.goal,
          capabilityScope: [...new Set(capabilityScope)],
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
