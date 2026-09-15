import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('structured intent exposes required V4 fields', () => {
  const intent = interpretTaskIntent('Open Settings')
  for (const key of ['objective', 'completionCriteria', 'forbiddenActions', 'targetPackages', 'executionMode', 'persistence', 'capabilityScope', 'riskClass', 'userConstraints']) {
    assert.ok(Object.hasOwn(intent, key), key)
  }
})
