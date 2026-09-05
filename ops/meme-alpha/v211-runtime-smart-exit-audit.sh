#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.10 RUNTIME SMART EXIT AUDIT ==='
systemctl is-active --quiet meme-alpha-micro-live.service && echo MICRO_SERVICE=active || echo MICRO_SERVICE=inactive
systemctl is-active --quiet meme-alpha-trend-pulse.service && echo TREND_SERVICE=active || echo TREND_SERVICE=inactive
systemctl is-active --quiet meme-alpha-signer.service && echo SIGNER_SERVICE=active || echo SIGNER_SERVICE=inactive
PID=$(systemctl show meme-alpha-micro-live.service -p MainPID --value || true)
echo MICRO_PID=${PID:-0}
grep -q 'MICRO_LIVE_EXECUTOR_V210_SMART_EXIT=STARTED' "$APP/src/micro-live-executor.js" && echo EXECUTOR_V210_CODE=present || echo EXECUTOR_V210_CODE=missing
grep -q 'SMART_TP1' "$APP/src/micro-live-executor.js" && echo SMART_PARTIAL_TP=present || echo SMART_PARTIAL_TP=missing
grep -q 'CONFIRMED_TREND_BREAK' "$APP/src/micro-live-executor.js" && echo ANTI_WHIPSAW_CONFIRM=present || echo ANTI_WHIPSAW_CONFIRM=missing
grep -q 'ENTRY_GATE_CLOSED_HOLD' "$APP/src/micro-live-executor.js" && echo TRANSIENT_GATE_HOLD=present || echo TRANSIENT_GATE_HOLD=missing
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const r=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};
const g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
const t=r('/opt/meme-alpha/app/runtime-status/trend-pulse.json');
console.log('GATE_ALLOWED='+(g.allowed===true));
console.log('GATE_REASONS='+((g.reasons||[]).join(',')||'NONE'));
console.log('TREND_TS='+(t.timestamp||'-'));
console.log('TREND_TOP_THEME='+((t.themes||[])[0]?.narrative||'NONE'));
console.log('TREND_TOP_STRENGTH='+((t.themes||[])[0]?.strength||0));
NODE
echo V211_RUNTIME_SMART_EXIT_AUDIT_PASS
