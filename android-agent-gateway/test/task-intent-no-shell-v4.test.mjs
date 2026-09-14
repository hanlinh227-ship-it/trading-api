import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent capability scope never includes raw shell', () => {
  const intent = interpretTaskIntent('Open Settings')
  assert.equal(intent.capabilityScope.includes('raw.shell'), false)
})
