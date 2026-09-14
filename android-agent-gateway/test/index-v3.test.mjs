import test from 'node:test'
import assert from 'node:assert/strict'
import { healthPayload } from '../src/index.js'

test('health advertises schema-2 task capability without private data', () => {
  const health = healthPayload({ DEPLOYMENT_SOURCE_SHA: 'abc123', AI: {} })
  assert.equal(health.ok, true)
  assert.equal(health.taskSchema, 2)
  assert.equal(health.plannerMode, 'workers-ai-with-deterministic-fallback')
  assert.equal(health.capabilities?.ephemeralScreenshots, true)
  assert.equal(health.capabilities?.localContacts, true)
  assert.equal('observation' in health, false)
  assert.equal('screenshot' in health, false)
})
