import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizedTaskInput } from '../src/index.js'

test('normalized task preserves user-stop persistence and explicit allowed package scope', () => {
  const task = normalizedTaskInput({
    goal: 'Play this game until I tell you to stop',
    allowedPackages: ['com.example.game', 'com.example.game'],
  }, 'github-oidc')

  assert.deepEqual(task.persistencePolicy, ['UNTIL_USER_STOP', 'UNTIL_APP_SCOPE_EXIT'])
  assert.deepEqual(task.allowedPackages, ['com.example.game'])
})

test('normalized task drops malformed package identifiers instead of widening app scope', () => {
  const task = normalizedTaskInput({
    goal: 'Open Settings and inspect it',
    allowedPackages: ['com.android.settings', '../other-app', '', 'com.android.settings'],
  }, 'github-oidc')

  assert.deepEqual(task.allowedPackages, ['com.android.settings'])
  assert.deepEqual(task.persistencePolicy, ['UNTIL_GOAL_COMPLETE'])
})
