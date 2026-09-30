import test from 'node:test'
import assert from 'node:assert/strict'
import { sanitizeMetrics } from '../src/cloud-escalation.js'

test('operational metrics exclude raw private content', () => {
  const metrics = sanitizeMetrics({
    localDecisionLatencyMs: 12,
    actionDispatchLatencyMs: 18,
    screenshot: 'data:image/png;base64,secret',
    privateMessageBody: 'secret',
  })
  assert.equal(metrics.screenshot, undefined)
  assert.equal(metrics.privateMessageBody, undefined)
  assert.equal(metrics.localDecisionLatencyMs, 12)
  assert.equal(metrics.actionDispatchLatencyMs, 18)
})
