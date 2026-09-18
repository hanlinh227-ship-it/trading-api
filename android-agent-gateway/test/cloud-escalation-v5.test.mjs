import test from 'node:test'
import assert from 'node:assert/strict'
import { boundMicroActions, sanitizeCheckpoint, sanitizeMetrics } from '../src/cloud-escalation.js'

test('micro-plan is bounded to eight actions', () => {
  const actions = Array.from({ length: 12 }, (_, index) => ({ type: 'wait', durationMs: index }))
  assert.equal(boundMicroActions(actions, 12).length, 8)
})

test('checkpoint drops raw private content and preserves bounded metadata', () => {
  const checkpoint = sanitizeCheckpoint({
    stepCount: 5,
    epoch: 1,
    checkpointCount: 2,
    screenSignature: 'screen-1',
    selectedSkillId: 'game2048',
    screenshot: 'secret',
    metrics: { localDecisionLatencyMs: 12, screenshot: 'secret' },
  })
  assert.equal(checkpoint.screenshot, undefined)
  assert.equal(checkpoint.metrics.screenshot, undefined)
  assert.equal(checkpoint.metrics.localDecisionLatencyMs, 12)
})

test('metric sanitizer keeps only numeric operational fields', () => {
  assert.deepEqual(sanitizeMetrics({ verifierLatencyMs: 8, rawPrompt: 'private', screenshotRate: 0.2 }), {
    verifierLatencyMs: 8,
    screenshotRate: 0.2,
  })
})
