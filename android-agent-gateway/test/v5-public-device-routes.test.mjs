import test from 'node:test'
import assert from 'node:assert/strict'
import worker from '../src/index.js'

function fixture() {
  const seen = []
  const stub = {
    async fetch(request) {
      seen.push({
        url: request.url,
        method: request.method,
        authorization: request.headers.get('authorization'),
        body: request.method === 'GET' ? null : await request.text(),
      })
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    },
  }
  const env = {
    DEVICE_SESSIONS: {
      idFromName(name) { return name },
      get() { return stub },
    },
  }
  return { env, seen }
}

for (const [publicOp, internalOp] of [
  ['checkpoint', 'task-checkpoint'],
  ['micro-plan', 'task-micro-plan'],
  ['recovery', 'task-recovery'],
]) {
  test(`V5 ${publicOp} route preserves device authentication and proxies to durable object`, async () => {
    const { env, seen } = fixture()
    const response = await worker.fetch(new Request(
      `https://gateway.example/v1/device/device%20one/tasks/task%2Fone/${publicOp}`,
      {
        method: 'POST',
        headers: {
          authorization: 'Bearer device-token',
          'content-type': 'application/json',
        },
        body: JSON.stringify({ observation: { fingerprint: 'fp-1' } }),
      },
    ), env)

    assert.equal(response.status, 200)
    assert.equal(seen.length, 1)
    assert.equal(new URL(seen[0].url).pathname, `/${internalOp}/task%2Fone`)
    assert.equal(seen[0].method, 'POST')
    assert.equal(seen[0].authorization, 'Bearer device-token')
  })
}

test('V5 device task operation routes reject non-POST methods before proxying', async () => {
  const { env, seen } = fixture()
  const response = await worker.fetch(new Request(
    'https://gateway.example/v1/device/device-1/tasks/task-1/checkpoint',
    { method: 'GET', headers: { authorization: 'Bearer device-token' } },
  ), env)
  assert.equal(response.status, 405)
  assert.equal(seen.length, 0)
})
