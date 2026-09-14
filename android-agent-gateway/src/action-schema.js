const INTEGER = value => Number.isInteger(value)
const STRING = value => typeof value === 'string' && value.length > 0
const DURATION = value => INTEGER(value) && value >= 50 && value <= 5000
const STROKE = value => value && typeof value === 'object' && !Array.isArray(value)
  && INTEGER(value.startX) && INTEGER(value.startY) && INTEGER(value.endX) && INTEGER(value.endY)
  && DURATION(value.durationMs)
const STROKES = value => Array.isArray(value) && value.length >= 1 && value.length <= 8 && value.every(STROKE)

const definitions = Object.freeze({
  launch_app: { riskClass: 'A', capability: 'apps.open', fields: { packageName: STRING } },
  click_node: { riskClass: 'A', capability: 'ui.navigate', fields: { selector: STRING } },
  long_click_node: { riskClass: 'A', capability: 'ui.navigate', fields: { selector: STRING } },
  read_screen: { riskClass: 'A', capability: 'ui.navigate', fields: {} },
  set_text: { riskClass: 'B', capability: 'ui.write', fields: { selector: STRING, value: value => typeof value === 'string' } },
  replace_text: { riskClass: 'B', capability: 'ui.write', fields: { selector: STRING, value: value => typeof value === 'string' } },
  clear_text: { riskClass: 'B', capability: 'ui.write', fields: { nodeId: STRING } },
  clipboard_set: { riskClass: 'B', capability: 'ui.write', fields: { value: value => typeof value === 'string' && value.length <= 16_384 } },
  clipboard_paste: { riskClass: 'B', capability: 'ui.write', fields: { selector: STRING } },
  select_text: {
    riskClass: 'B', capability: 'ui.write',
    fields: { selector: STRING, start: value => INTEGER(value) && value >= 0, end: value => INTEGER(value) && value >= 0 },
  },
  global_back: { riskClass: 'A', capability: 'ui.navigate', fields: {} },
  global_home: { riskClass: 'A', capability: 'ui.navigate', fields: {} },
  global_recents: { riskClass: 'A', capability: 'ui.navigate', fields: {} },
  global_notifications: { riskClass: 'A', capability: 'ui.navigate', fields: {} },
  global_quick_settings: { riskClass: 'A', capability: 'ui.navigate', fields: {} },
  swipe: {
    riskClass: 'A', capability: 'ui.navigate',
    fields: { startX: INTEGER, startY: INTEGER, endX: INTEGER, endY: INTEGER, durationMs: value => INTEGER(value) && value >= 50 && value <= 3000 },
  },
  drag: {
    riskClass: 'A', capability: 'ui.navigate',
    fields: { startX: INTEGER, startY: INTEGER, endX: INTEGER, endY: INTEGER, durationMs: DURATION },
  },
  multi_stroke_gesture: { riskClass: 'A', capability: 'ui.navigate', fields: { strokes: STROKES } },
  tap_point: { riskClass: 'A', capability: 'ui.navigate', fields: { x: INTEGER, y: INTEGER } },
  long_press_point: {
    riskClass: 'A', capability: 'ui.navigate',
    fields: { x: INTEGER, y: INTEGER, durationMs: value => INTEGER(value) && value >= 500 && value <= 3000 },
  },
  double_tap_point: { riskClass: 'A', capability: 'ui.navigate', fields: { x: INTEGER, y: INTEGER } },
  scroll_node: {
    riskClass: 'A', capability: 'ui.navigate',
    fields: { nodeId: STRING, direction: value => value === 'FORWARD' || value === 'BACKWARD' },
  },
  wait: { riskClass: 'A', capability: 'ui.navigate', fields: { durationMs: value => INTEGER(value) && value >= 0 && value <= 5000 } },
  open_url: { riskClass: 'A', capability: 'apps.open', fields: { url: STRING } },
  send_message: { riskClass: 'C', capability: 'ui.destructive.confirmed', fields: { contact: STRING, message: value => typeof value === 'string' } },
  delete_data: { riskClass: 'C', capability: 'ui.destructive.confirmed', fields: { itemCount: value => INTEGER(value) && value >= 1 } },
  wallet_sign: { riskClass: 'D', capability: 'security.denied', fields: { payload: STRING } },
})

export function actionDefinition(type) {
  return definitions[type] ?? null
}

export function validateTypedAction(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('invalid_action')
  const definition = actionDefinition(input.type)
  if (!definition) throw new Error('unknown_action')
  const output = { type: input.type }
  for (const [field, validate] of Object.entries(definition.fields)) {
    if (!validate(input[field])) throw new Error(`invalid_action_field:${field}`)
    output[field] = input[field]
  }
  if (output.type === 'select_text' && output.end < output.start) throw new Error('invalid_action_field:end')
  return output
}

export function typedActionMetadata(input) {
  const action = validateTypedAction(input)
  const definition = actionDefinition(action.type)
  return { action, riskClass: definition.riskClass, capability: definition.capability }
}
