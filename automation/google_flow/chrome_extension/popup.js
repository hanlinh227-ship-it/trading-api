const $ = (id) => document.getElementById(id);

function send(message) {
  return chrome.runtime.sendMessage(message);
}

function statusText(config) {
  const s = config?.currentStatus || {};
  const mode = config?.autopilotEnabled ? (config.paused ? 'ON · PAUSED' : 'ON') : 'OFF';
  return `${mode} · ${s.state || 'idle'}${s.error_code ? ` · ${s.error_code}` : ''}`;
}

async function load() {
  const res = await send({ type:'GET_CONFIG' });
  if (!res?.ok) {
    $('status').textContent = res?.error_code || 'Không đọc được cấu hình';
    return;
  }
  const c = res.config;
  $('autopilotToggle').checked = !!c.autopilotEnabled;
  $('commandBusUrl').value = c.commandBusUrl || res.defaultCommandBusUrl || '';
  $('pollMinutes').value = c.pollMinutes || 1;
  $('promptSelector').value = c.calibration?.prompt?.selector || '';
  $('generateSelector').value = c.calibration?.generate?.selector || '';
  $('downloadSelector').value = c.calibration?.download?.selector || '';
  $('status').textContent = statusText(c);
  $('lastCommand').textContent = c.currentStatus?.command_id ? `Command: ${c.currentStatus.command_id}` : 'Chưa có command đang hoạt động.';
}

function calibrationFromInputs() {
  const mk = (value) => value.trim() ? { selector:value.trim() } : null;
  return {
    prompt: mk($('promptSelector').value),
    generate: mk($('generateSelector').value),
    download: mk($('downloadSelector').value)
  };
}

async function saveConfig() {
  const res = await send({
    type:'SET_CONFIG',
    commandBusUrl:$('commandBusUrl').value.trim(),
    pollMinutes:Number($('pollMinutes').value || 1),
    calibration:calibrationFromInputs()
  });
  $('status').textContent = res?.ok ? statusText(res.config) : (res?.error_code || 'Lưu thất bại');
  return res;
}

$('autopilotToggle').addEventListener('change', async (event) => {
  await saveConfig();
  const res = await send({ type:'SET_AUTOPILOT', enabled:event.target.checked });
  $('status').textContent = res?.ok ? statusText(res.config) : (res?.error_code || 'Không đổi được Autopilot');
});

$('saveConfig').addEventListener('click', saveConfig);
$('pollNow').addEventListener('click', async () => {
  await saveConfig();
  $('status').textContent = 'Đang poll queue…';
  const res = await send({ type:'POLL_NOW' });
  $('status').textContent = res?.ok ? 'Poll đã chạy.' : (res?.error_code || 'Poll lỗi');
  await load();
});

$('runPreflight').addEventListener('click', async () => {
  await saveConfig();
  const [tab] = await chrome.tabs.query({ active:true, currentWindow:true });
  if (!tab?.id) {
    $('preflightResult').textContent = 'Không tìm thấy tab hiện tại.';
    return;
  }
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { type:'RUN_PREFLIGHT', calibration:calibrationFromInputs() });
    $('preflightResult').textContent = response?.ok
      ? 'PASS: prompt + Generate resolve duy nhất, không thấy blocker.'
      : `BLOCKED: prompt=${response?.prompt}, generate=${response?.generate}, blocker=${response?.blocker || 'none'}`;
  } catch (error) {
    $('preflightResult').textContent = `Không kết nối được content script: ${error.message}`;
  }
});

$('pauseBtn').addEventListener('click', async () => { await send({type:'PAUSE_AUTOPILOT'}); await load(); });
$('resumeBtn').addEventListener('click', async () => { await send({type:'RESUME_AUTOPILOT'}); await load(); });
$('stopBtn').addEventListener('click', async () => { await send({type:'STOP_AUTOPILOT'}); await load(); });

load();
setInterval(load, 2500);

$('exportLog').addEventListener('click', async () => {
  const res = await send({ type:'GET_STATUS' });
  if (!res?.ok) return;
  const payload = {
    exported_at:new Date().toISOString(),
    currentStatus:res.config.currentStatus,
    history:res.config.history
  };
  const url = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(payload, null, 2))}`;
  await chrome.downloads.download({ url, filename:`flow-autopilot-log-${Date.now()}.json`, saveAs:true });
});

$('clearInflight').addEventListener('click', async () => {
  const confirmed = confirm('Clear mọi command đang preflight/submitted/waiting? Chỉ dùng khi tab Flow bị đóng/reload hoặc trạng thái bị kẹt.');
  if (!confirmed) return;
  await send({ type:'CLEAR_INFLIGHT' });
  await load();
});
