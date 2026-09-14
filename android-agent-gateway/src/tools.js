const RISK_D = [
  'otp', '2fa', 'password', 'mật khẩu', 'private key', 'seed phrase', 'seed',
  'wallet sign', 'ký ví', 'transfer money', 'chuyển tiền', 'withdraw', 'rút tiền',
  'banking', 'ngân hàng', 'disable security', 'tắt bảo mật'
]
const RISK_C = [
  'delete', 'xóa', 'uninstall', 'gỡ ứng dụng', 'purchase', 'buy ', 'mua ', 'publish', 'đăng công khai',
  'move to trash', 'trash', 'chuyển vào thùng rác', 'thùng rác',
  'send message', 'send the message', 'gửi tin', 'gửi lời', 'gửi message'
]
const RISK_B = [
  'type ', 'enter text', 'write text', 'draft ', 'fill in',
  'nhập ', 'gõ ', 'điền ', 'soạn nháp', 'viết nháp',
  'upload', 'tải lên', 'change setting', 'đổi cài đặt'
]

export function classifyGoal(goal) {
  const text = String(goal ?? '').toLowerCase()
  if (RISK_D.some(x => text.includes(x))) return 'D'
  if (RISK_C.some(x => text.includes(x))) return 'C'
  if (RISK_B.some(x => text.includes(x))) return 'B'
  return 'A'
}

export function validateRunGoal(input) {
  if (!input || typeof input !== 'object') throw new Error('input required')
  const allowedKeys = new Set(['deviceId', 'goal', 'capabilityScope', 'riskCeiling', 'confirmedRiskClassC'])
  for (const key of Object.keys(input)) {
    if (!allowedKeys.has(key)) throw new Error(`unsupported field: ${key}`)
  }
  if (typeof input.deviceId !== 'string' || !input.deviceId.trim()) throw new Error('deviceId required')
  if (typeof input.goal !== 'string' || !input.goal.trim()) throw new Error('goal required')
  if (input.confirmedRiskClassC != null && typeof input.confirmedRiskClassC !== 'boolean') {
    throw new Error('confirmedRiskClassC must be boolean')
  }
  return {
    deviceId: input.deviceId.trim(),
    goal: input.goal.trim(),
    capabilityScope: Array.isArray(input.capabilityScope) ? input.capabilityScope : ['apps.open', 'ui.navigate'],
    riskCeiling: input.riskCeiling ?? 'C',
    confirmedRiskClassC: input.confirmedRiskClassC === true,
  }
}

export const TOOL_CONTRACT = Object.freeze({
  android_device_status: { write: false },
  android_run_goal: { write: true, rawShell: false },
  android_get_task: { write: false },
  android_confirm_action: { write: true },
  android_cancel_task: { write: true },
})
