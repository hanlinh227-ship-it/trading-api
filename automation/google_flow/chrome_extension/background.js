import { validateQueue, isAllowedFlowUrl } from './lib/queue.js';
import { nextRunnableCommand, markState, clearInflight } from './lib/state.js';

const DEFAULT_COMMAND_BUS_URL = 'https://raw.githubusercontent.com/hanlinh227-ship-it/trading-api/automation/google-flow-command-bus/automation/google_flow/queue.json';
const DEFAULTS = Object.freeze({
  autopilotEnabled: false,
  commandBusUrl: DEFAULT_COMMAND_BUS_URL,
  pollMinutes: 1,
  paused: false,
  calibration: { prompt: null, generate: null, download: null },
  history: { items: {}, order: [] },
  currentStatus: { state: 'idle', command_id: null, error_code: null, updated_at: null }
});

async function readStore() {
  const data = await chrome.storage.local.get(Object.keys(DEFAULTS));
  return {
    autopilotEnabled: data.autopilotEnabled ?? DEFAULTS.autopilotEnabled,
    commandBusUrl: data.commandBusUrl ?? DEFAULTS.commandBusUrl,
    pollMinutes: Number(data.pollMinutes ?? DEFAULTS.pollMinutes),
    paused: data.paused ?? DEFAULTS.paused,
    calibration: data.calibration ?? DEFAULTS.calibration,
    history: data.history ?? DEFAULTS.history,
    currentStatus: data.currentStatus ?? DEFAULTS.currentStatus
  };
}

async function writeStatus(state, commandId = null, errorCode = null) {
  const status = {
    state,
    command_id: commandId,
    error_code: errorCode,
    updated_at: new Date().toISOString()
  };
  await chrome.storage.local.set({ currentStatus: status });
  return status;
}

function canonicalCommandBus(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && parsed.hostname === 'raw.githubusercontent.com';
  } catch {
    return false;
  }
}

async function installDefaults() {
  const existing = await chrome.storage.local.get(Object.keys(DEFAULTS));
  const updates = {};
  for (const [key, value] of Object.entries(DEFAULTS)) {
    if (existing[key] === undefined) updates[key] = value;
  }
  if (Object.keys(updates).length) await chrome.storage.local.set(updates);
  await scheduleAlarm();
}

async function scheduleAlarm() {
  const cfg = await readStore();
  await chrome.alarms.clear('flow-autopilot-poll');
  if (!cfg.autopilotEnabled) return;
  const periodInMinutes = Math.max(1, Number(cfg.pollMinutes) || 1);
  chrome.alarms.create('flow-autopilot-poll', { delayInMinutes: 0.05, periodInMinutes });
}

async function fetchQueue(url) {
  if (!canonicalCommandBus(url)) throw new Error('COMMAND_BUS_URL_REJECTED');
  const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`COMMAND_BUS_HTTP_${response.status}`);
  return response.json();
}

async function findFlowTab(projectUrl) {
  const tabs = await chrome.tabs.query({});
  const exact = tabs.find(tab => tab.url === projectUrl);
  if (exact) return exact;
  const flow = tabs.find(tab => isAllowedFlowUrl(tab.url || ''));
  return flow || null;
}

async function waitForTabReady(tabId, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === 'complete') return tab;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error('FLOW_TAB_TIMEOUT');
}

async function ensureFlowTab(projectUrl) {
  if (!isAllowedFlowUrl(projectUrl)) throw new Error('PROJECT_URL_REJECTED');
  let tab = await findFlowTab(projectUrl);
  if (!tab) {
    tab = await chrome.tabs.create({ url: projectUrl, active: false });
    return waitForTabReady(tab.id);
  }
  if (tab.url !== projectUrl) {
    tab = await chrome.tabs.update(tab.id, { url: projectUrl });
    return waitForTabReady(tab.id);
  }
  return tab;
}

async function recordCommandState(command, state, errorCode = null) {
  const cfg = await readStore();
  const existing = cfg.history.items?.[command.command_id];
  const attempts = state === 'preflight' ? Number(existing?.attempts || 0) + 1 : Number(existing?.attempts || 0);
  const history = markState(cfg.history, command.command_id, state, {
    scene: command.scene,
    attempts,
    error_code: errorCode,
    received_at: existing?.received_at || new Date().toISOString()
  });
  await chrome.storage.local.set({ history });
  await writeStatus(state, command.command_id, errorCode);
}

async function dispatchCommand(command) {
  await recordCommandState(command, 'preflight');
  const tab = await ensureFlowTab(command.project_url);
  const cfg = await readStore();
  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: 'EXECUTE_RENDER_COMMAND',
      command,
      calibration: cfg.calibration
    });
    if (!response?.ok) {
      const code = response?.error_code || 'CONTENT_EXECUTION_FAILED';
      await recordCommandState(command, response?.state || 'blocked', code);
      return { ok: false, error_code: code };
    }
    await recordCommandState(command, response.state || 'submitted');
    return { ok: true, state: response.state || 'submitted' };
  } catch (error) {
    await recordCommandState(command, 'blocked', 'CONTENT_SCRIPT_UNAVAILABLE');
    return { ok: false, error_code: 'CONTENT_SCRIPT_UNAVAILABLE', message: error?.message };
  }
}

async function pollOnce() {
  const cfg = await readStore();
  if (!cfg.autopilotEnabled || cfg.paused) return { ok: true, skipped: true, reason: 'disabled-or-paused' };
  await writeStatus('polling');
  let queue;
  try {
    queue = await fetchQueue(cfg.commandBusUrl);
  } catch (error) {
    await writeStatus('blocked', null, error.message || 'QUEUE_FETCH_FAILED');
    return { ok: false, error_code: error.message || 'QUEUE_FETCH_FAILED' };
  }

  const validated = validateQueue(queue, Date.now());
  if (!validated.ok) {
    await writeStatus('blocked', null, 'QUEUE_INVALID');
    return { ok: false, error_code: 'QUEUE_INVALID', errors: validated.errors };
  }

  const command = nextRunnableCommand(validated.commands, cfg.history, Date.now());
  if (!command) {
    await writeStatus('idle');
    return { ok: true, idle: true };
  }
  return dispatchCommand(command);
}

chrome.runtime.onInstalled.addListener(() => { installDefaults(); });
chrome.runtime.onStartup.addListener(() => { scheduleAlarm(); });
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'flow-autopilot-poll') pollOnce();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    switch (message?.type) {
      case 'GET_CONFIG':
        return { ok: true, config: await readStore(), defaultCommandBusUrl: DEFAULT_COMMAND_BUS_URL };
      case 'SET_AUTOPILOT':
        await chrome.storage.local.set({ autopilotEnabled: !!message.enabled, paused: false });
        await scheduleAlarm();
        return { ok: true, config: await readStore() };
      case 'SET_CONFIG': {
        const updates = {};
        if (typeof message.commandBusUrl === 'string') {
          if (!canonicalCommandBus(message.commandBusUrl)) return { ok: false, error_code: 'COMMAND_BUS_URL_REJECTED' };
          updates.commandBusUrl = message.commandBusUrl;
        }
        if (message.pollMinutes != null) updates.pollMinutes = Math.max(1, Number(message.pollMinutes) || 1);
        if (message.calibration) updates.calibration = message.calibration;
        await chrome.storage.local.set(updates);
        await scheduleAlarm();
        return { ok: true, config: await readStore() };
      }
      case 'POLL_NOW':
        return pollOnce();
      case 'GET_STATUS':
        return { ok: true, config: await readStore() };
      case 'PAUSE_AUTOPILOT':
        await chrome.storage.local.set({ paused: true });
        return { ok: true };
      case 'RESUME_AUTOPILOT':
        await chrome.storage.local.set({ paused: false });
        return { ok: true, result: await pollOnce() };
      case 'STOP_AUTOPILOT':
        await chrome.storage.local.set({ autopilotEnabled: false, paused: false });
        await scheduleAlarm();
        return { ok: true };
      case 'CLEAR_INFLIGHT': {
        const cfg = await readStore();
        const history = clearInflight(cfg.history, Date.now());
        await chrome.storage.local.set({ history });
        await writeStatus('idle', null, null);
        return { ok: true, history };
      }
      case 'EXECUTION_STATE': {
        if (!message.command_id || !message.state) return { ok: false, error_code: 'INVALID_STATE_MESSAGE' };
        const cfg = await readStore();
        const history = markState(cfg.history, message.command_id, message.state, {
          scene: message.scene,
          attempts: cfg.history.items?.[message.command_id]?.attempts || 1,
          error_code: message.error_code || null,
          received_at: cfg.history.items?.[message.command_id]?.received_at || new Date().toISOString()
        });
        await chrome.storage.local.set({ history });
        await writeStatus(message.state, message.command_id, message.error_code || null);
        return { ok: true };
      }
      case 'DOWNLOAD_URL': {
        if (!message.url || !/^https:/i.test(message.url)) return { ok: false, error_code: 'DOWNLOAD_URL_REJECTED' };
        const id = await chrome.downloads.download({ url: message.url, filename: message.filename || undefined, saveAs: false });
        return { ok: true, downloadId: id };
      }
      default:
        return { ok: false, error_code: 'UNSUPPORTED_MESSAGE' };
    }
  })().then(sendResponse).catch(error => sendResponse({ ok: false, error_code: 'BACKGROUND_ERROR', message: error?.message || String(error) }));
  return true;
});
