import test from 'node:test'
import assert from 'node:assert/strict'
import { plan2048Step } from '../src/game-2048-planner.js'

test('2048 keeps swiping when accessibility fingerprint cannot observe Canvas changes', () => {
  const plan = plan2048Step(
    { stepCount: 5, recoveryCount: 4, persistence: 'UNTIL_TERMINAL' },
    { screenWidth: 1080, screenHeight: 2400, nodes: [] },
  )
  assert.equal(plan.action.type, 'swipe')
  assert.equal(plan.expectedPostcondition.type, 'observation_returned')
})

test('2048 still stops on an explicit game-over signal', () => {
  const plan = plan2048Step(
    { stepCount: 50, recoveryCount: 0 },
    { nodes: [{ text: 'Game Over!' }] },
  )
  assert.equal(plan.expectedPostcondition.type, 'task_complete')
})
