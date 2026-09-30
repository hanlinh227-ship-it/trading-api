import test from 'node:test'
import assert from 'node:assert/strict'
import { migrateV4Skill } from '../src/app-skill-memory.js'

test('v4 memory is a hint and cannot widen risk', () => {
  const migrated = migrateV4Skill({
    packageName: 'com.example',
    riskClass: 'C',
    confidence: 1,
    actionTemplate: [{ action: { type: 'tap_point', x: 100, y: 200 } }],
  })
  assert.equal(migrated.authority, 'HINT_ONLY')
  assert.equal(migrated.requiresCurrentAuthorization, true)
  assert.equal(migrated.requiresRegrounding, true)
  assert.equal(migrated.riskClass, 'C')
  assert.ok(migrated.confidence < 0.8)
})

test('v4 coordinate-only recipes stay low confidence', () => {
  const migrated = migrateV4Skill({
    packageName: 'com.example',
    riskClass: 'A',
    confidence: 0.99,
    actionTemplate: [{ action: { type: 'tap_point', x: 100, y: 200 } }],
  })
  assert.ok(migrated.confidence <= 0.55)
  assert.equal(migrated.requiresRegrounding, true)
})
