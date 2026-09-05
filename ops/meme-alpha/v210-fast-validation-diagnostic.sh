#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
R=$APP/runtime-status
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_RUNNER; exit 1; }
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=n=>{try{return JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'))}catch{return null}};
const sig=read('signal-snapshot.json')||{},v=read('validation.json')||{},s=read('stress-test.json')||{},u=read('universe.json')||{},g=read('micro-live-gate.json')||{};
const cs=Array.isArray(sig.candidates)?sig.candidates:[];
const cnt=(fn)=>cs.filter(fn).length;
console.log('=== FAST VALIDATION DIAGNOSTIC ===');
console.log(`SIGNAL_VERSION=${sig.version||'MISSING'}`);
console.log(`SOURCE_STATUS=${sig.sourceHealth?.status||'MISSING'} SOURCES=${sig.sourceHealth?.successfulSources??-1} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`CANDIDATES=${cs.length}`);
console.log(`MEME_CONFIRMED=${cnt(x=>x.universeClass==='MEME_CONFIRMED')}`);
console.log(`SECURITY_PASS=${cnt(x=>x.securityDecision==='PASS')}`);
console.log(`PROBE_CANDIDATE=${cnt(x=>x.decision==='PROBE_CANDIDATE')}`);
console.log(`SELLABLE=${cnt(x=>x.sellRoute===true)}`);
console.log(`PERSIST_READY=${cnt(x=>['READY','PROBE','ELIGIBLE'].includes(String(x.persistenceDecision||'').toUpperCase()))}`);
console.log(`STRICT_READY=${cnt(x=>x.universeClass==='MEME_CONFIRMED'&&x.securityDecision==='PASS'&&x.decision==='PROBE_CANDIDATE'&&x.sellRoute===true&&!x.token2022&&(x.hardReject||[]).length===0&&Number(x.score)>=70&&Number(x.liquidityUsd)>=25000&&['READY','PROBE','ELIGIBLE'].includes(String(x.persistenceDecision||'').toUpperCase()))}`);
console.log(`VALIDATION_STATUS=${v.readinessStatus||'MISSING'} COMPLETED=${Number(v.completedLifecycleTrades||0)}`);
console.log(`STRESS_STATUS=${s.status||'MISSING'} FAIL=${Number(s.fail??-1)}`);
console.log(`UNIVERSE=${u.version||'MISSING'} UNKNOWN_ENTRY_ELIGIBLE=${u.unknownEntryEligible}`);
console.log(`MICRO_GATE=${g.allowed} REASONS=${(g.reasons||[]).join('|')}`);
for(const x of cs.slice(0,30)) console.log(`CAND ${x.symbol||'?'} score=${x.score} class=${x.universeClass} sec=${x.securityDecision} decision=${x.decision} sell=${x.sellRoute} liq=${Math.round(Number(x.liquidityUsd||0))} persist=${x.persistenceDecision||'-'} streak=${x.consecutiveEligible||0} reject=${(x.hardReject||[]).join(';')||'-'}`);
console.log('V210_DIAGNOSTIC_PASS');
NODE
