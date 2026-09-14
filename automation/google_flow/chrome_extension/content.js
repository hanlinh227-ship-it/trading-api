(async () => {
  const [{ resolveCalibratedTarget, detectBlockingState }, { preflightRender, executeRenderCurrent, captureCompletionSnapshot, detectCompletionSignal }] = await Promise.all([
    import(chrome.runtime.getURL('lib/dom_adapter.js')),
    import(chrome.runtime.getURL('lib/executor.js'))
  ]);

  async function notifyState(command, state, errorCode = null) {
    try {
      await chrome.runtime.sendMessage({
        type: 'EXECUTION_STATE',
        command_id: command.command_id,
        scene: command.scene,
        state,
        error_code: errorCode
      });
    } catch {
      // Service worker may be suspended; the direct response still carries state.
    }
  }

  async function monitorCompletion(command, calibration, beforeSnapshot, timeoutMs = 600000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      await new Promise(resolve => setTimeout(resolve, 3000));
      const blocker = detectBlockingState(document);
      if (blocker) {
        await notifyState(command, 'blocked', blocker);
        return;
      }
      const after = captureCompletionSnapshot(document, calibration?.download);
      const signal = detectCompletionSignal(beforeSnapshot, after);
      if (signal) {
        await notifyState(command, 'completed');
        return;
      }
    }
    await notifyState(command, 'blocked', 'COMPLETION_NOT_OBSERVED');
  }

  async function executeCommand(command, calibration) {
    const prompt = resolveCalibratedTarget(document, calibration?.prompt, 'prompt');
    const generate = resolveCalibratedTarget(document, calibration?.generate, 'generate');
    const blocker = detectBlockingState(document);
    const preflight = preflightRender(command, { href: location.href, blockingState: blocker }, { prompt, generate });
    if (!preflight.ok) {
      const errorCode = preflight.errors[0] || 'PREFLIGHT_FAILED';
      await notifyState(command, 'blocked', errorCode);
      return { ok: false, state: 'blocked', error_code: errorCode, errors: preflight.errors };
    }

    try {
      const beforeSnapshot = captureCompletionSnapshot(document, calibration?.download);
      await executeRenderCurrent(command, { prompt: prompt.element, generate: generate.element });
      await notifyState(command, 'submitted');
      monitorCompletion(command, calibration, beforeSnapshot);
      return { ok: true, state: 'submitted' };
    } catch (error) {
      const errorCode = error?.message || 'EXECUTION_FAILED';
      await notifyState(command, 'failed', errorCode);
      return { ok: false, state: 'failed', error_code: errorCode };
    }
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'EXECUTE_RENDER_COMMAND') {
      executeCommand(message.command, message.calibration).then(sendResponse);
      return true;
    }
    if (message?.type === 'RUN_PREFLIGHT') {
      const prompt = resolveCalibratedTarget(document, message.calibration?.prompt, 'prompt');
      const generate = resolveCalibratedTarget(document, message.calibration?.generate, 'generate');
      sendResponse({
        ok: prompt.ok && generate.ok && !detectBlockingState(document),
        prompt: prompt.ok ? 'ok' : prompt.errorCode,
        generate: generate.ok ? 'ok' : generate.errorCode,
        blocker: detectBlockingState(document)
      });
      return false;
    }
  });

  // Faster foreground polling while Flow is open; background dedupe prevents duplicate submission.
  setInterval(async () => {
    try {
      const status = await chrome.runtime.sendMessage({ type: 'GET_STATUS' });
      if (status?.config?.autopilotEnabled && !status?.config?.paused) {
        await chrome.runtime.sendMessage({ type: 'POLL_NOW' });
      }
    } catch {
      // Ignore transient service-worker lifecycle errors.
    }
  }, 15000);
})();
