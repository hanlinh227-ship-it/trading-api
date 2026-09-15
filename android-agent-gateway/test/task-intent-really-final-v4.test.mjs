import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent risk is one of known classes', () => {
  assert.ok(['A','B','C','D'].includes(interpretTaskIntent('Open Settings').riskClass))
})
