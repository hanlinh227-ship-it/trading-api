#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LOG=/var/log/meme-alpha/paper.log
ERR=/var/log/meme-alpha/paper-error.log
cd "$APP"
echo '=== V1.3.1 STDERR ROOT-CAUSE DIAGNOSTIC ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs'; const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8')); if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER'); console.log('MODE=PAPER');
NODE
echo '=== STDERR RECENT ==='
tail -260 "$ERR" || true
echo '=== STDERR FILTERED ==='
tail -1200 "$ERR" | grep -nE -C 5 'Error|ERROR|ReferenceError|TypeError|SyntaxError|ENOENT|EACCES|429|timeout|ETIMEDOUT|fetch failed|ECONN|MODULE_NOT_FOUND|JSON' || true
echo '=== STDOUT RECENT FAILURE MARKERS ==='
tail -650 "$LOG" | grep -nE -C 4 'FULL_CYCLE_FAILED|FULL_CYCLE_COMPLETE|PERSISTENCE_STATUS|REACTION_TELEMETRY_STATUS|RISK_STATUS' || true
echo '=== SERVICE PROCESS ==='
systemctl --no-pager status meme-alpha-paper.service | tail -30 || true
echo 'V131_STDERR_DIAGNOSTIC_COMPLETE'
