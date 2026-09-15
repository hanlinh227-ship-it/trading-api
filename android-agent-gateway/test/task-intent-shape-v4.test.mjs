import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('intent execution mode is one of supported V4 modes', () => {
  const mode = interpretTaskIntent('Open Settings').executionMode
  assert.ok(['AUTO','SEMANTIC','VISUAL','HYBRID','DETERMINISTIC'].includes(mode))
})
