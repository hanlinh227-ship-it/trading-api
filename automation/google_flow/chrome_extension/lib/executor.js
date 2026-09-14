import { isAllowedFlowUrl } from './queue.js';

const EXECUTABLE_ASSET_MODES = new Set(['current', 'none']);

export function preflightRender(command, pageContext = {}, targets = {}) {
  const errors = [];
  if (!command || command.action !== 'render') errors.push('ACTION_UNSUPPORTED');
  if (!isAllowedFlowUrl(command?.project_url || '')) errors.push('PROJECT_URL_REJECTED');
  if (!isAllowedFlowUrl(pageContext?.href || '')) errors.push('PAGE_ORIGIN_REJECTED');
  if (pageContext?.blockingState) errors.push(pageContext.blockingState);

  for (const [slot, asset] of [['START', command?.start_image], ['END', command?.end_image]]) {
    const mode = asset?.mode || 'none';
    if (!EXECUTABLE_ASSET_MODES.has(mode)) errors.push(`ASSET_MODE_UNSUPPORTED_${slot}_${String(mode).toUpperCase()}`);
  }

  if (!targets?.prompt?.ok || !targets.prompt.element) errors.push('PROMPT_TARGET_MISSING');
  if (!targets?.generate?.ok || !targets.generate.element) errors.push('GENERATE_TARGET_MISSING');
  if (targets?.generate?.element?.disabled) errors.push('GENERATE_DISABLED');
  if (!String(command?.prompt || '').trim()) errors.push('PROMPT_EMPTY');

  return { ok: errors.length === 0, errors };
}

function dispatchInputEvents(element) {
  element.dispatchEvent?.(new Event('input', { bubbles: true }));
  element.dispatchEvent?.(new Event('change', { bubbles: true }));
}

function fillPromptElement(element, prompt) {
  element.focus?.();
  if ('value' in element && !element.isContentEditable) {
    element.value = prompt;
    dispatchInputEvents(element);
    return;
  }
  element.textContent = prompt;
  element.dispatchEvent?.(new InputEvent('input', { bubbles: true, data: prompt, inputType: 'insertText' }));
}

export async function executeRenderCurrent(command, targets = {}) {
  const promptTarget = targets.prompt;
  const generateTarget = targets.generate;
  if (!promptTarget) throw new Error('PROMPT_TARGET_MISSING');
  if (!generateTarget) throw new Error('GENERATE_TARGET_MISSING');
  if (generateTarget.disabled) throw new Error('GENERATE_DISABLED');
  fillPromptElement(promptTarget, command.prompt);
  await Promise.resolve();
  generateTarget.click();
  return { submitted: true };
}

export function captureCompletionSnapshot(documentLike, downloadCalibration = null) {
  let downloadCount = 0;
  const selector = downloadCalibration?.selector;
  if (selector) {
    try {
      downloadCount = [...(documentLike?.querySelectorAll?.(selector) || [])]
        .filter(el => {
          if (typeof el?.getBoundingClientRect !== 'function') return true;
          const rect = el.getBoundingClientRect();
          return rect?.width > 0 && rect?.height > 0;
        }).length;
    } catch {
      downloadCount = 0;
    }
  }
  const videoSrcs = [...(documentLike?.querySelectorAll?.('video[src]') || [])]
    .map(el => el?.src || el?.getAttribute?.('src') || '')
    .filter(Boolean);
  return { downloadCount, videoSrcs };
}

export function detectCompletionSignal(before = {}, after = {}) {
  if (Number(after.downloadCount || 0) > Number(before.downloadCount || 0)) return 'download';
  const previous = new Set(before.videoSrcs || []);
  if ((after.videoSrcs || []).some(src => src && !previous.has(src))) return 'video';
  return null;
}
