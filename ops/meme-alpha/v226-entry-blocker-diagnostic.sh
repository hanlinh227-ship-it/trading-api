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
const sig=read(`${R}/signal-snapshot.json`),v=read(`${R}/validation.json`),g=read(`${R}/micro-live-gate.json`);
const directRisk=read(`${P}/risk-state.json`),risk=Object.keys(directRisk).length?directRisk:(sig.risk||{}),ms=read(`${M}/state.json`);
console.log('=== MEME ALPHA CURRENT LIVE + CAPITAL FLOW DIAGNOSTIC ===');
console.log(`GATE_ALLOWED=${!!g.allowed} GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'} EXEC=${g.executionMode||'-'} ARM=${!!g.armOk}`);
console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`LIVE_RISK_SIGNAL=${risk.riskRegime||'-'} PAPER_BLOCK=${(risk.globalBlockReasons||[]).join(',')||'NONE'}`);
console.log(`RUNNER_CAN_READ_MICRO_STATE=${Object.keys(ms).length>0}`);
if(Object.keys(ms).length){
  const cap=ms.capital||{},lam=n=>Number.isFinite(Number(n))?Number(n):0;
  console.log(`BOT_OBSERVED_SOL=${(lam(cap.lastObservedSolLamports)/1e9).toFixed(9)}`);
  console.log(`DEPOSITS_DETECTED_SOL=${(lam(cap.depositsLamports)/1e9).toFixed(9)}`);
  console.log(`WITHDRAWALS_DETECTED_SOL=${(lam(cap.withdrawalsLamports)/1e9).toFixed(9)}`);
  console.log(`NET_EXTERNAL_FLOW_SOL=${(lam(cap.netExternalFlowLamports)/1e9).toFixed(9)}`);
  console.log(`LAST_EXTERNAL_FLOW_AT=${cap.lastExternalFlowAt||'NONE'}`);
  console.log(`MICRO_POSITION=${ms.position?.symbol||'NONE'} CLOSED=${ms.closed||0}`);
}
console.log(`COMPLETED=${Number(v.completedLifecycleTrades||0)} VALIDATION=${v.readinessStatus||'-'}`);
NODE

echo '=== MICRO EXECUTOR SERVICE ==='
printf 'MICRO_SERVICE_ACTIVE='; systemctl is-active meme-alpha-micro-live.service || true
systemctl show meme-alpha-micro-live.service -p ActiveState -p SubState -p MainPID -p User -p ExecMainStartTimestamp --no-pager || true
printf 'MICRO_DATA_DIR_PERMS='; stat -c '%U:%G %a' /var/lib/meme-alpha/data/micro-live 2>/dev/null || echo INACCESSIBLE
printf 'MICRO_STATE_PATH_TEST='; if test -f /var/lib/meme-alpha/data/micro-live/state.json; then echo EXISTS; else echo NOT_VISIBLE_TO_RUNNER; fi

echo '=== PUBLIC CHAIN BALANCE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
const pub='DpdTfAAyrtQm28CBgi1xH3Euk1xHAJsnmSiqUMGVNSfk';
const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'getBalance',params:[pub,{commitment:'confirmed'}]}),signal:AbortSignal.timeout(12000)});
const j=await r.json();
if(j.error) throw new Error('RPC_BALANCE_'+JSON.stringify(j.error));
const lam=Number(j?.result?.value||0);
console.log(`CHAIN_BALANCE_LAMPORTS=${lam}`);
console.log(`CHAIN_BALANCE_SOL=${(lam/1e9).toFixed(9)}`);
NODE

echo '=== RECENT MICRO SERVICE STATUS ==='
systemctl status meme-alpha-micro-live.service --no-pager -n 25 2>&1 | tail -n 35 || true

echo CURRENT_CAPITAL_FLOW_DIAGNOSTIC_PASS
