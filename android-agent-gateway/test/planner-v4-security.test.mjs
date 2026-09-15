import test from 'node:test'
import assert from 'node:assert/strict'
import { clampPlan } from '../src/planner.js'

test('planner cannot execute an action explicitly forbidden by task intent', () => {
  const plan = {
    action: { type: 'click_node', selector: 'n:purchase' },
    expected: { type: 'observation_changed' },
    expectedPostcondition: { type: 'observation_changed' },
    requiredCapabilities: ['ui.navigate'],
    riskClass: 'A',
  }
  assert.throws(
    () => clampPlan(plan, ['ui.navigate'], 'C', { forbiddenActions: ['PURCHASE'], contextualAction: 'PURCHASE' }),
    /forbidden_action/i,
  )
})
