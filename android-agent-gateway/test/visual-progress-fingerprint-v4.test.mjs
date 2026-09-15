import test from 'node:test'
import assert from 'node:assert/strict'
import { observationFingerprint } from '../src/device-session.js'

test('visual-only screen changes produce a different task observation fingerprint', () => {
  const semantic = 'same-accessibility-tree'
  const before = observationFingerprint({ fingerprint: semantic, screenshotHash: 'shot-a' })
  const after = observationFingerprint({ fingerprint: semantic, screenshotHash: 'shot-b' })
  assert.notEqual(before, after)
})

test('semantic fingerprint remains usable when screenshot is unavailable', () => {
  assert.equal(observationFingerprint({ fingerprint: 'semantic-a' }), 'semantic-a')
})
