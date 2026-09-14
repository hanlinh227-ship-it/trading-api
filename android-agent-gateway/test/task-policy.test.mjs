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
    taskId: 't1', goal: 'navigate settings', capabilityScope: ['ui.navigate'], riskClass: 'A',
  })
  assert.throws(() => clampTaskStep({ task, action: { type: 'set_text', selector: 'n:0.1', value: 'x' } }), /capability/i)
  assert.throws(() => clampTaskStep({ task, action: { type: 'wallet_sign', payload: 'x' } }), /class_d/i)
})

test('class C action requires confirmation bound to the same task', () => {
  const base = createTaskState({
    taskId: 't-delete', goal: 'delete selected item', capabilityScope: ['ui.destructive.confirmed'], riskClass: 'C',
  })
  assert.throws(() => clampTaskStep({ task: base, action: { type: 'delete_data', itemCount: 1 } }), /confirmation/i)

  const confirmed = { ...base, confirmedRiskClassC: true, confirmedTaskId: 't-delete' }
  assert.equal(clampTaskStep({ task: confirmed, action: { type: 'delete_data', itemCount: 1 } }).riskClass, 'C')

  const wrongBinding = { ...confirmed, confirmedTaskId: 'other' }
  assert.throws(() => clampTaskStep({ task: wrongBinding, action: { type: 'delete_data', itemCount: 1 } }), /confirmation/i)
})

test('bounded task progress enforces 40 steps and 5 recoveries', () => {
  let task = createTaskState({ taskId: 't2', goal: 'safe nav', capabilityScope: ['ui.navigate'], riskClass: 'A' })
  for (let i = 0; i < 40; i += 1) task = recordTaskProgress(task, { kind: 'step' })
  assert.throws(() => recordTaskProgress(task, { kind: 'step' }), /max_steps/i)

  let recovering = createTaskState({ taskId: 't3', goal: 'safe nav', capabilityScope: ['ui.navigate'], riskClass: 'A' })
  for (let i = 0; i < 5; i += 1) recovering = recordTaskProgress(recovering, { kind: 'recovery' })
  assert.throws(() => recordTaskProgress(recovering, { kind: 'recovery' }), /max_recoveries/i)
})
