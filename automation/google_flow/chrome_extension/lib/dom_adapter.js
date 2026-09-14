function isVisible(element) {
  if (!element || typeof element.getBoundingClientRect !== 'function') return false;
  const rect = element.getBoundingClientRect();
  return !!rect && rect.width > 0 && rect.height > 0;
}

function codePrefix(kind) {
  return String(kind || 'target').toUpperCase();
}

export function resolveCalibratedTarget(documentLike, calibration = {}, kind = 'target') {
  const prefix = codePrefix(kind);
  const selector = calibration?.selector;
  if (!selector) return { ok:false, errorCode:`${prefix}_UNCALIBRATED` };
  let matches = [];
  try {
    matches = [...(documentLike?.querySelectorAll?.(selector) || [])].filter(isVisible);
  } catch {
    return { ok:false, errorCode:`${prefix}_INVALID_SELECTOR` };
  }
  if (matches.length === 0) return { ok:false, errorCode:`${prefix}_NOT_FOUND` };
  if (matches.length > 1) return { ok:false, errorCode:`${prefix}_AMBIGUOUS` };
  const element = matches[0];
  if (kind === 'generate' && element.disabled) return { ok:false, errorCode:'GENERATE_DISABLED' };
  return { ok:true, element };
}

export function detectBlockingState(documentLike) {
  const text = `${documentLike?.body?.innerText || ''} ${documentLike?.body?.textContent || ''}`.toLowerCase();
  if (/sign in|log in|đăng nhập|choose an account/.test(text)) return 'LOGIN_REQUIRED';
  if (/captcha|verify you are human|robot|unusual traffic/.test(text)) return 'CAPTCHA_REQUIRED';
  if (/no credits|credits remaining|out of credits|quota exceeded|limit reached|hết credit/.test(text)) return 'QUOTA_EXHAUSTED';
  return null;
}

export function preflightDom(documentLike, calibration = {}) {
  const errors = [];
  const blocker = detectBlockingState(documentLike);
  if (blocker) errors.push(blocker);

  const prompt = resolveCalibratedTarget(documentLike, calibration.prompt, 'prompt');
  if (!prompt.ok) errors.push(prompt.errorCode);
  const generate = resolveCalibratedTarget(documentLike, calibration.generate, 'generate');
  if (!generate.ok) errors.push(generate.errorCode);

  return { ok: errors.length === 0, errors };
}
