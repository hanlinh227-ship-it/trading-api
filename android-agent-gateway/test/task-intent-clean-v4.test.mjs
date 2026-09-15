import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent objective trims surrounding whitespace', () => {
  assert.equal(interpretTaskIntent('  Open Settings  ').objective, 'Open Settings')
})
