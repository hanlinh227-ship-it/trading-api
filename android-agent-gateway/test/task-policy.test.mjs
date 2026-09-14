import test from 'node:test'
import assert from 'node:assert/strict'
import { validateTypedAction } from '../src/action-schema.js'
import { clampTaskStep, createTaskState, recordTaskProgress } from '../src/task-policy.js'

test('typed action validation normalizes known actions and rejects malformed input', () => {
  assert.deepEqual(validateTypedAction({ type: 'tap_point', x: 12, y: 34 }), { type: 'tap_point', x: 12, y: 34 })
  assert.deepEqual(validateTypedAction({ type: 'global_back' }), { type: 'global_back' })
  assert.throws(() => validateTypedAction({ type: 'tap_point', x: 12 }))
  assert.throws(() => validateTypedAction({ type: 'unknown_action' }))
})

test('task policy rejects capability escalation and class D actions', () => {
  const task = createTaskState({
    taskId: 't1', goal: 'navigate settings', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A',
  })
  assert.throws(() => clampTaskStep({ task, action: { type: 'set_text', selector: 'n:0.1', value: 'x' } }), /capability/i)
  assert.throws(() => clampTaskStep({ task, action: { type: 'wallet_sign', payload: 'x' } }), /class_d/i)
})

test('task risk is a monotonic floor while riskClass remains the ceiling', () => {
  const task = createTaskState({
    taskId: 't-write',
    goal: 'type a draft',
    capabilityScope: ['apps.open', 'ui.navigate', 'ui.write'],
    riskClass: 'B',
    taskRiskClass: 'B',
  })
  const step = clampTaskStep({ task, action: { type: 'launch_app', packageName: 'com.example' } })
  assert.equal(step.riskClass, 'B')
  assert.equal(step.capability, 'apps.open')
})

test('contextual destructive target cannot hide behind class A click action', () => {
  const observation = {
    packageName: 'com.example',
    windowTitle: 'Inbox',
    nodes: [{
      nodeId: 'n:0.2', text: 'Delete', contentDescription: null, resourceId: 'delete_button',
      visibleToUser: true, clickable: true, checkable: false,
      bounds: { left: 0, top: 0, right: 100, bottom: 100 },
    }],
  }
  const safeTask = createTaskState({
    taskId: 't-safe', goal: 'inspect inbox', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A',
  })
  assert.throws(
    () => clampTaskStep({ task: safeTask, action: { type: 'click_node', selector: 'n:0.2' }, observation }),
    /risk_escalation/i,
  )

  const confirmed = createTaskState({
    taskId: 't-delete',
    goal: 'delete selected item',
    capabilityScope: ['ui.navigate', 'ui.destructive.confirmed'],
    riskClass: 'C',
    taskRiskClass: 'C',
    confirmedRiskClassC: true,
    confirmedTaskId: 't-delete',
  })
  assert.equal(
    clampTaskStep({ task: confirmed, action: { type: 'click_node', selector: 'n:0.2' }, observation }).riskClass,
    'C',
  )
})

test('coordinate tap inherits contextual switch mutation risk', () => {
  const observation = {
    packageName: 'com.android.settings',
    windowTitle: 'Display',
    nodes: [{
      nodeId: 'n:0.1', text: 'Dark theme', contentDescription: null, resourceId: 'dark_theme',
      className: 'android.widget.Switch', visibleToUser: true, clickable: true, checkable: true,
      bounds: { left: 10, top: 10, right: 200, bottom: 80 },
    }],
  }
  const safeTask = createTaskState({
    taskId: 't-look', goal: 'inspect display', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A',
  })
  assert.throws(
    () => clampTaskStep({ task: safeTask, action: { type: 'tap_point', x: 50, y: 40 }, observation }),
    /risk_escalation/i,
  )
})

test('class C action requires confirmation bound to the same task', () => {
  const base = createTaskState({
    taskId: 't-delete', goal: 'delete selected item', capabilityScope: ['ui.destructive.confirmed'], riskClass: 'C', taskRiskClass: 'C',
  })
  assert.throws(() => clampTaskStep({ task: base, action: { type: 'delete_data', itemCount: 1 } }), /confirmation/i)

  const confirmed = { ...base, confirmedRiskClassC: true, confirmedTaskId: 't-delete' }
  assert.equal(clampTaskStep({ task: confirmed, action: { type: 'delete_data', itemCount: 1 } }).riskClass, 'C')

  const wrongBinding = { ...confirmed, confirmedTaskId: 'other' }
  assert.throws(() => clampTaskStep({ task: wrongBinding, action: { type: 'delete_data', itemCount: 1 } }), /confirmation/i)
})

test('bounded task progress uses 50-action epochs and preserves five-recovery limit', () => {
  let task = createTaskState({ taskId: 't2', goal: 'safe nav', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A' })
  for (let i = 0; i < 50; i += 1) task = recordTaskProgress(task, { kind: 'step', progressMarker: `p-${i}` })
  assert.equal(task.epoch, 1)
  assert.equal(task.epochStepCount, 0)
  assert.equal(task.checkpointCount, 1)

  let recovering = createTaskState({ taskId: 't3', goal: 'safe nav', capabilityScope: ['ui.navigate'], riskClass: 'A', taskRiskClass: 'A' })
  for (let i = 0; i < 5; i += 1) recovering = recordTaskProgress(recovering, { kind: 'recovery' })
  assert.throws(() => recordTaskProgress(recovering, { kind: 'recovery' }), /max_recoveries/i)
})
