const NEGATION = String.raw`(?:do\s+not|don't|dont|never|without|không|đừng|chưa)`

function normalize(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function unique(values) {
  return [...new Set(values.filter(Boolean))]
}

function negatedTerm(text, termPattern) {
  return new RegExp(`${NEGATION}[^.!?;]{0,180}(?:${termPattern})`, 'iu').test(text)
}

function extractForbiddenActions(text) {
  const out = []
  if (negatedTerm(text, String.raw`buy|purchase|pay|checkout|mua|thanh\s*toán`)) out.push('PURCHASE')
  if (negatedTerm(text, String.raw`delete|remove|erase|trash|xóa|xoá|gỡ`)) out.push('DELETE')
  if (negatedTerm(text, String.raw`send|submit|publish|post|share|gửi|đăng`)) out.push('SEND')
  if (negatedTerm(text, String.raw`ad(?:s|vertisement)?|quảng\s*cáo`)) out.push('OPEN_AD')
  if (negatedTerm(text, String.raw`external\s+(?:link|url)|link\s+outside|liên\s+kết\s+ngoài`)) out.push('OPEN_EXTERNAL_LINK')
  if (negatedTerm(text, String.raw`password|passcode|otp|2fa|mfa|private\s+key|seed\s+phrase|recovery\s+phrase|mật\s*khẩu|mã\s*otp|khóa\s*riêng|khoá\s*riêng|cụm\s*từ\s*khôi\s*phục`)) out.push('CREDENTIAL_ACCESS')
  if (negatedTerm(text, String.raw`wallet\s*(?:sign|signature)|sign\s+(?:(?:any|a)\s+)?wallet|sign\s+(?:a\s+)?transaction|ký\s*ví`)) out.push('WALLET_SIGN')
  return unique(out)
}

function stripNegatedClauses(text) {
  const pattern = new RegExp(`${NEGATION}[^.!?;]*`, 'giu')
  return text.replace(pattern, ' ')
}

function requestedRisk(text) {
  const requested = stripNegatedClauses(text).toLowerCase()
  const d = /\b(?:otp|2fa|mfa|password|passcode|private key|seed phrase|recovery phrase|wallet sign|sign wallet|sign transaction|transfer money|withdraw|banking)\b|mật khẩu|mã otp|mã pin|khóa riêng|khoá riêng|cụm từ khôi phục|ký ví|chuyển tiền|rút tiền|ngân hàng/u
  const c = /\b(?:delete|remove|erase|trash|uninstall|purchase|buy|pay|checkout|send|submit|publish|post|share publicly)\b|xóa|xoá|gỡ ứng dụng|mua|thanh toán|gửi|đăng công khai/u
  const b = /\b(?:type|enter text|write text|draft|fill|save|apply|edit|rename|toggle|switch|enable|disable|turn on|turn off|upload|change setting|change dark mode)\b|nhập|gõ|điền|soạn nháp|viết nháp|lưu|áp dụng|chỉnh|đổi tên|bật|tắt/u
  if (d.test(requested)) return 'D'
  if (c.test(requested)) return 'C'
  if (b.test(requested)) return 'B'
  return 'A'
}

function extractConstraints(text) {
  const pattern = new RegExp(`${NEGATION}[^.!?;]*`, 'giu')
  return unique([...text.matchAll(pattern)].map(match => normalize(match[0])))
}

function intentShape(objective) {
  const lower = objective.toLowerCase()
  const forbiddenActions = extractForbiddenActions(objective)
  const userConstraints = extractConstraints(objective)
  const riskClass = requestedRisk(objective)
  const is2048 = /(?:^|\D)2048(?:\D|$)/u.test(lower)
  const gameLike = is2048 || /\b(?:play|game|puzzle)\b|\bchơi\b|trò chơi/u.test(lower)
  const terminalPhrase = /game\s*over|until\s+(?:it|the game)\s+ends?|until[^.!?;]*(?:over|ends?)|đến\s+khi[^.!?;]*(?:thua|kết\s*thúc)|cho\s+đến\s+khi[^.!?;]*(?:thua|kết\s*thúc)/u.test(lower)
  const userStopPhrase = /until\s+(?:i\s+)?(?:say|tell\s+you\s+to|ask\s+you\s+to)?\s*stop|until\s+i\s+stop|keep[^.!?;]*until[^.!?;]*stop|only\s+stop[^.!?;]*(?:i\s+say|when\s+i)|chỉ\s+(?:khi|đến\s+khi)[^.!?;]*tôi[^.!?;]*(?:nói\s+)?dừng|đến\s+khi\s+tôi\s+(?:nói\s+)?dừng|cho\s+đến\s+khi\s+tôi\s+(?:nói\s+)?dừng|khi\s+tôi\s+bảo\s+dừng/u.test(lower)
  const longPhrase = /\b(?:keep|repeat|repetitive|continuously|continue|until|finished|complete|all the way)\b|tiếp tục|lặp|đến khi|cho đến khi|làm hết|toàn bộ/u.test(lower)
  const multiStep = /\bthen\b|\band then\b|\bsau đó\b|\brồi\b|,\s*(?:find|inspect|fill|summarize|go|open|then)\b/u.test(lower)

  let persistence = 'ONE_SHOT'
  if (userStopPhrase) persistence = 'LONG_RUNNING'
  else if (gameLike && terminalPhrase) persistence = 'UNTIL_TERMINAL'
  else if (gameLike || longPhrase) persistence = 'LONG_RUNNING'
  else if (multiStep) persistence = 'LONG_RUNNING'

  let executionMode = 'SEMANTIC'
  let deterministicAdapter = null
  if (is2048) {
    executionMode = 'DETERMINISTIC'
    deterministicAdapter = '2048'
  } else if (/\bwebview\b/u.test(lower)) {
    executionMode = 'HYBRID'
  } else if (gameLike || /custom\s+(?:ui|screen)|canvas|surfaceview/u.test(lower)) {
    executionMode = 'VISUAL'
  }

  const capabilityScope = ['ui.navigate']
  if (riskClass === 'B' || riskClass === 'C') capabilityScope.push('ui.write')
  if (riskClass === 'C') capabilityScope.push('ui.destructive.confirmed')

  const persistencePolicy = userStopPhrase
    ? ['UNTIL_USER_STOP', 'UNTIL_APP_SCOPE_EXIT']
    : ['UNTIL_GOAL_COMPLETE']
  const completionCriteria = userStopPhrase
    ? ['USER_STOP_OR_APP_SCOPE_EXIT']
    : persistence === 'UNTIL_TERMINAL'
      ? [gameLike ? 'GAME_TERMINAL' : 'TASK_TERMINAL']
      : persistence === 'LONG_RUNNING'
        ? ['OBJECTIVE_COMPLETE']
        : ['ACTION_VERIFIED']

  return {
    intentSchema: 5,
    objective,
    completionCriteria,
    forbiddenActions,
    targetPackages: [],
    allowedPackages: [],
    executionMode,
    deterministicAdapter,
    persistence,
    persistencePolicy,
    capabilityScope: unique(capabilityScope),
    riskClass,
    userConstraints,
    gameLike,
    multiStep,
    userStopPhrase,
  }
}

export function interpretTaskIntent(goal) {
  const objective = normalize(goal)
  if (!objective) throw new Error('goal_required')
  return intentShape(objective)
}

export function shouldUseTaskPath(intent) {
  if (!intent || typeof intent !== 'object') throw new Error('intent_required')
  return intent.persistence !== 'ONE_SHOT'
    || intent.riskClass !== 'A'
    || intent.executionMode === 'VISUAL'
    || intent.executionMode === 'HYBRID'
    || intent.executionMode === 'DETERMINISTIC'
    || intent.gameLike === true
    || intent.multiStep === true
}

export function bridgeDispatchPlan(goal) {
  const intent = interpretTaskIntent(goal)
  const task = shouldUseTaskPath(intent)
  return { path: task ? 'tasks' : 'commands', schema: task ? 2 : 1, intent }
}
