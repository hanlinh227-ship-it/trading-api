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
const cs=Array.isArray(sig.candidates)?sig.candidates:[];const cnt=fn=>cs.filter(fn).length;
console.log('=== FAST VALIDATION DIAGNOSTIC ===');
console.log(`SIGNAL_VERSION=${sig.version||'MISSING'}`);console.log(`SOURCE_STATUS=${sig.sourceHealth?.status||'MISSING'} SOURCES=${sig.sourceHealth?.successfulSources??-1} CACHE=${sig.sourceHealth?.usingCache}`);console.log(`CANDIDATES=${cs.length} MEME_CONFIRMED=${cnt(x=>x.universeClass==='MEME_CONFIRMED')} SECURITY_PASS=${cnt(x=>x.securityDecision==='PASS')} PROBE_CANDIDATE=${cnt(x=>x.decision==='PROBE_CANDIDATE')} SELLABLE=${cnt(x=>x.sellRoute===true)} FAST_TRACK=${cnt(x=>x.fastTrackReady===true)} PAPER_READY=${cnt(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);console.log(`VALIDATION_STATUS=${v.readinessStatus||'MISSING'} COMPLETED=${Number(v.completedLifecycleTrades||0)}`);console.log(`STRESS_STATUS=${s.status||'MISSING'} FAIL=${Number(s.fail??-1)}`);console.log(`UNIVERSE=${u.version||'MISSING'} UNKNOWN_ENTRY_ELIGIBLE=${u.unknownEntryEligible}`);console.log(`MICRO_GATE=${g.allowed} REASONS=${(g.reasons||[]).join('|')}`);
for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,20)) console.log(`MEME ${x.symbol||'?'} score=${x.score} sec=${x.securityDecision} decision=${x.decision} t22=${x.token2022} top=${x.topHoldersPct} sell=${x.sellRoute} impact=${x.sellPriceImpactPct} persist=${x.persistenceDecision||'-'} streak=${x.consecutiveEligible||0} fast=${x.fastTrackReady} secReview=${(x.securityReviewReasons||[]).join(';')||'-'} secBlock=${(x.securityBlockReasons||[]).join(';')||'-'} holder=${x.holderAuditDecision||'-'} holderReview=${(x.holderReviewReasons||[]).join(';')||'-'} holderBlock=${(x.holderBlockReasons||[]).join(';')||'-'}`);
console.log('V210_DIAGNOSTIC_PASS');
NODE
