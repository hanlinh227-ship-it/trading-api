import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent exposes target package array without inventing package ids', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.ok(Array.isArray(intent.targetPackages))
})
