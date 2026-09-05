#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
BOT_PUB='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk'
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const P='/var/lib/meme-alpha/data/paper';
const M='/var/lib/meme-alpha/data/micro-live';
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sig=read(`${R}/signal-snapshot.json`),g=read(`${R}/micro-live-gate.json`),risk=read(`${P}/risk-state.json`),ms=read(`${M}/state.json`);
console.log('=== MEME ALPHA LIVE CAPITAL DETECTION DIAGNOSTIC ===');
console.log(`GATE_ALLOWED=${!!g.allowed} EXEC=${g.executionMode||'-'} ARM=${!!g.armOk} REASONS=${(g.reasons||[]).join(',')||'NONE'}`);
console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`RUNNER_CAN_READ_MICRO_STATE=${Object.keys(ms).length>0}`);
console.log(`PAPER_RISK_BLOCK=${(risk.globalBlockReasons||[]).join(',')||'NONE'}`);
NODE

echo '=== MICRO EXECUTOR SERVICE ==='
printf 'MICRO_SERVICE_ACTIVE='; systemctl is-active meme-alpha-micro-live.service || true
systemctl show meme-alpha-micro-live.service -p ActiveState -p SubState -p MainPID -p User -p ExecMainStartTimestamp -p StandardOutput -p StandardError --no-pager || true

echo '=== MICRO UNIT ==='
systemctl cat meme-alpha-micro-live.service --no-pager 2>&1 || true

echo '=== PUBLIC CHAIN BALANCE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
const pub='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk';
const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'getBalance',params:[pub,{commitment:'confirmed'}]}),signal:AbortSignal.timeout(12000)});
const j=await r.json(); if(j.error) throw new Error(JSON.stringify(j.error));
const lam=Number(j.result.value); console.log(`CHAIN_BALANCE_SOL=${(lam/1e9).toFixed(9)}`);
NODE

echo '=== MICRO LOG DISCOVERY ==='
for f in /var/log/meme-alpha/micro-live.log /var/log/meme-alpha/micro-live-error.log /var/log/meme-alpha/micro.log /var/log/meme-alpha/micro-error.log; do
  if [ -r "$f" ]; then
    echo "READABLE_LOG=$f"
    tail -n 80 "$f" | grep -E 'ACTION=|CAPITAL_|MICRO_|EXECUTOR_|STARTED|WAIT|BUY|SELL' | tail -n 35 || true
  fi
done

echo '=== JOURNAL RECENT ==='
journalctl -u meme-alpha-micro-live.service --no-pager -n 40 2>&1 | tail -n 45 || true

echo CURRENT_CAPITAL_RUNTIME_TRACE_PASS
