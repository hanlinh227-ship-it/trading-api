import { typedActionMetadata } from './action-schema.js'

const EXPECTED_TYPES = new Set([
  'observation_changed',
  'observation_returned',
  'foreground_package',
  'node_visible',
  'node_missing',
  'text_present',
  'text_missing',
  'task_complete',
])

function cleanExpected(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('invalid_planner_expected')
  if (typeof input.type !== 'string' || !EXPECTED_TYPES.has(input.type)) throw new Error('invalid_planner_expected_type')
  const out = { type: input.type }
  for (const key of ['packageName', 'nodeId', 'fingerprint', 'text']) {
    if (input[key] !== undefined) {
      if (typeof input[key] !== 'string' || input[key].length > 256) throw new Error(`invalid_planner_expected_field:${key}`)
      out[key] = input[key]
    }
  }
  return out
}

export function parsePlannerModelResponse(raw) {
  let value = raw
  if (typeof value === 'string') value = JSON.parse(value)
  if (value?.response !== undefined) value = typeof value.response === 'string' ? JSON.parse(value.response) : value.response
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid_planner_response')

  const metadata = typedActionMetadata(value.action)
  const expected = cleanExpected(value.expected)
  const rationaleCode = value.rationaleCode == null ? null : String(value.rationaleCode)
  if (rationaleCode && !/^[A-Z0-9_:-]{1,64}$/.test(rationaleCode)) throw new Error('invalid_planner_rationale_code')

  return {
    action: metadata.action,
    expected,
    rationaleCode,
    riskClass: metadata.riskClass,
    requiredCapabilities: [metadata.capability],
  }
}

export const PLANNER_JSON_SCHEMA = Object.freeze({
  type: 'object',
  additionalProperties: false,
  required: ['action', 'expected', 'rationaleCode'],
  properties: {
    action: { type: 'object' },
    expected: {
      type: 'object',
      required: ['type'],
      additionalProperties: true,
      properties: { type: { type: 'string' } },
    },
    rationaleCode: { type: 'string', maxLength: 64 },
  },
})
