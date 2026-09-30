import test from 'node:test'
import assert from 'node:assert/strict'
import { clampTaskStep, createTaskState } from '../src/task-policy.js'

test('persistent V5 cannot downgrade class C task authority', () => {
  const task = createTaskState({
    taskId: 'security-c',
    goal: 'delete selected item',
    capabilityScope: ['apps.open', 'ui.navigate', 'ui.destructive.confirmed'],
    riskClass: 'C',
    taskRiskClass: 'C',
    confirmedRiskClassC: true,
    confirmedTaskId: 'security-c',
    persistencePolicy: ['UNTIL_USER_STOP'],
  })

  const step = clampTaskStep({
    task,
    action: { type: 'launch_app', packageName: 'com.example.safe' },
  })

  assert.equal(step.riskClass, 'C')
})

test('persistent V5 never allows class D unattended action', () => {
  const task = createTaskState({
    taskId: 'security-d',
    goal: 'navigate safely',
    capabilityScope: ['ui.navigate'],
    riskClass: 'A',
    taskRiskClass: 'A',
    persistencePolicy: ['UNTIL_USER_STOP'],
  })

  assert.throws(
    () => clampTaskStep({ task, action: { type: 'wallet_sign', payload: 'x' } }),
    /class_d_denied/,
  )
})
