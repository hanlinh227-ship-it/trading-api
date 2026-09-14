import test from 'node:test'
import assert from 'node:assert/strict'
import { typedActionMetadata, validateTypedAction } from '../src/action-schema.js'

test('V4 generic actions validate with stable capabilities and risks', () => {
  assert.deepEqual(validateTypedAction({ type: 'drag', startX: 1, startY: 2, endX: 3, endY: 4, durationMs: 500 }), {
    type: 'drag', startX: 1, startY: 2, endX: 3, endY: 4, durationMs: 500,
  })
  assert.equal(typedActionMetadata({ type: 'replace_text', selector: 'n:0.1', value: 'hello' }).riskClass, 'B')
  assert.equal(typedActionMetadata({ type: 'clipboard_set', value: 'hello' }).capability, 'ui.write')
  assert.equal(typedActionMetadata({ type: 'clipboard_paste', selector: 'n:0.1' }).riskClass, 'B')
})

test('bounded multi-stroke gesture validates individual strokes', () => {
  const action = validateTypedAction({
    type: 'multi_stroke_gesture',
    strokes: [
      { startX: 10, startY: 10, endX: 100, endY: 100, durationMs: 300 },
      { startX: 20, startY: 20, endX: 120, endY: 120, durationMs: 350 },
    ],
  })
  assert.equal(action.strokes.length, 2)
  assert.throws(() => validateTypedAction({ type: 'multi_stroke_gesture', strokes: [] }))
  assert.throws(() => validateTypedAction({ type: 'multi_stroke_gesture', strokes: new Array(9).fill({ startX: 0, startY: 0, endX: 1, endY: 1, durationMs: 100 }) }))
})
