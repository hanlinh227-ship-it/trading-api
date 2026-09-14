import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('inspection-only goal stays class A', () => {
  assert.equal(interpretTaskIntent('Open Messages and inspect spam').riskClass, 'A')
})
