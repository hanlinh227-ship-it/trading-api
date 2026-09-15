import test from 'node:test'
import assert from 'node:assert/strict'
import { selectExecutionMode } from '../src/mode-router.js'

test('semantic nodes are preferred for ordinary app workflows', () => {
  const mode = selectExecutionMode(
    { executionMode: 'AUTO', objective: 'open settings' },
    { packageName: 'com.android.settings', nodes: [{ nodeId: 'n:0', clickable: true }] },
  )
  assert.equal(mode, 'SEMANTIC')
})

test('game/canvas tasks fall back to visual when semantic tree is empty', () => {
  const mode = selectExecutionMode(
    { executionMode: 'AUTO', objective: 'play puzzle', gameLike: true },
    { packageName: 'com.game', nodes: [], screenshotAvailable: true },
  )
  assert.equal(mode, 'VISUAL')
})

test('2048 routes to deterministic fast path', () => {
  const mode = selectExecutionMode(
    { executionMode: 'DETERMINISTIC', deterministicAdapter: '2048' },
    { packageName: 'org.example.game2048', nodes: [], screenshotAvailable: true },
  )
  assert.equal(mode, 'DETERMINISTIC')
})

test('hybrid is selected when both semantic and screenshot context materially exist', () => {
  const mode = selectExecutionMode(
    { executionMode: 'HYBRID', objective: 'operate custom webview' },
    { nodes: [{ nodeId: 'n:0' }], screenshotAvailable: true },
  )
  assert.equal(mode, 'HYBRID')
})
