import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('custom WebView goal can request hybrid execution', () => {
  const intent = interpretTaskIntent('Use this WebView form and fill it without submitting')
  assert.equal(intent.executionMode, 'HYBRID')
  assert.equal(intent.riskClass, 'B')
})
