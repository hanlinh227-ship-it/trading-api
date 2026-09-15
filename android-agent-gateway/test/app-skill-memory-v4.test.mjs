import test from 'node:test'
import assert from 'node:assert/strict'
import { candidateFromTrajectory, groundSkill } from '../src/app-skill-memory.js'

test('successful safe trajectory can produce an app-scoped reusable recipe', () => {
  const skill = candidateFromTrajectory({
    task: { taskId: 't1', taskRiskClass: 'A', riskClass: 'A', goal: 'open display settings' },
    packageName: 'com.android.settings',
    history: [
      { action: { type: 'click_node', selector: 'n:0.2' }, semanticAnchor: { text: 'Display', resourceId: 'display_settings' }, verified: true },
      { action: { type: 'read_screen' }, semanticAnchor: { text: 'Dark theme' }, verified: true },
    ],
  })
  assert.equal(skill.packageName, 'com.android.settings')
  assert.ok(skill.actionTemplate.length >= 1)
  assert.ok(skill.confidence > 0)
})

test('class C and D trajectories are never learned', () => {
  assert.equal(candidateFromTrajectory({
    task: { taskId: 't2', taskRiskClass: 'C', riskClass: 'C', goal: 'delete data' },
    packageName: 'com.example', history: [{ action: { type: 'click_node', selector: 'n:1' }, verified: true }],
  }), null)
})

test('skill replay re-grounds by current semantic anchor instead of stale node id', () => {
  const skill = {
    packageName: 'com.android.settings', intentPattern: 'display', requiredCapabilities: ['ui.navigate'],
    actionTemplate: [{ action: { type: 'click_node', selector: 'n:old' }, semanticAnchor: { text: 'Display', resourceId: 'display_settings' } }],
    confidence: 0.8,
  }
  const grounded = groundSkill(skill, {
    packageName: 'com.android.settings',
    nodes: [{ nodeId: 'n:new', text: 'Display', resourceId: 'display_settings', clickable: true }],
  })
  assert.equal(grounded[0].selector, 'n:new')
})

test('missing anchors or wrong package fail closed to general planning', () => {
  const skill = {
    packageName: 'com.android.settings', actionTemplate: [{ action: { type: 'click_node', selector: 'n:old' }, semanticAnchor: { text: 'Display' } }], confidence: 0.8,
  }
  assert.equal(groundSkill(skill, { packageName: 'com.other', nodes: [] }), null)
  assert.equal(groundSkill(skill, { packageName: 'com.android.settings', nodes: [] }), null)
})
