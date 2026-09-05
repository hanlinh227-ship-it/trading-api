#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/micro-live
cd "$APP"
echo '=== MEME ALPHA v2.5.0 CAPITAL FLOW INSPECTION ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_ANALYSIS_ENGINE_NOT_PAPER');
console.log('ANALYSIS_MODE=PAPER');
NODE
printf '%s\n' '=== MICRO EXECUTOR SOURCE ==='
sed -n '1,520p' src/micro-live-executor.js
printf '%s\n' '=== MICRO POLICY ==='
cat /etc/meme-alpha/micro-live-policy.json 2>/dev/null || echo MICRO_POLICY_MISSING
printf '%s\n' '=== MICRO STATE ==='
cat "$DATA/state.json" 2>/dev/null || echo MICRO_STATE_MISSING
printf '%s\n' '=== GATE ==='
cat runtime-status/micro-live-gate.json 2>/dev/null || echo GATE_MISSING
printf '%s\n' '=== SERVICES ==='
systemctl --no-pager is-active meme-alpha-paper.service || true
systemctl --no-pager is-active meme-alpha-signer.service || true
systemctl --no-pager is-active meme-alpha-micro-live.service || true
printf '%s\n' '=== KEY SAFETY ==='
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo RUNNER_KEY_ACCESS=UNSAFE; exit 1; else echo RUNNER_KEY_ACCESS=BLOCKED; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo RUNNER_SIGNER_ACCESS=UNSAFE; exit 1; else echo RUNNER_SIGNER_ACCESS=BLOCKED; fi
echo NETWORK_EXECUTION_PERFORMED=FALSE
echo V250_CAPITAL_FLOW_INSPECTION_PASS
