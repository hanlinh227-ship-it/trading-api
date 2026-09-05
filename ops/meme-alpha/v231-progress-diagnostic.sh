#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
R=$APP/runtime-status
D=/var/lib/meme-alpha/data/paper
cd "$APP"

echo '=== MEME ALPHA v2.3.1 PROGRESS DIAGNOSTIC ==='
date -u '+UTC_NOW=%Y-%m-%dT%H:%M:%SZ'
systemctl is-active --quiet meme-alpha-paper.service && echo PAPER_SERVICE=ACTIVE || echo PAPER_SERVICE=INACTIVE
systemctl is-enabled --quiet meme-alpha-paper.service && echo PAPER_ENABLED=TRUE || echo PAPER_ENABLED=FALSE

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=n=>{try{return JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'))}catch{return null}};
const sig=read('signal-snapshot.json');
const v=read('validation.json');
const s=read('stress-test.json');
const g=read('micro-live-gate.json');
if(sig){
 const cs=sig.candidates||[], n=f=>cs.filter(f).length;
 const age=Math.max(0,(Date.now()-Date.parse(sig.generatedAt||sig.checkedAt||0))/1000);
 console.log(`SIGNAL_VERSION=${sig.version}`);
 console.log(`SIGNAL_AGE_SEC=${Number.isFinite(age)?age.toFixed(1):'NA'}`);
 console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAILED=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);
 console.log(`CANDIDATES=${cs.length} MEME=${n(x=>x.universeClass==='MEME_CONFIRMED')} SEC_PASS=${n(x=>x.securityDecision==='PASS')} HOLDER_PASS=${n(x=>x.holderClusterDecision==='PASS')} SELL_TRUE=${n(x=>x.sellRoute===true)} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);
 for(const x of cs.filter(x=>x.decision==='PROBE_CANDIDATE'||x.persistenceDecision==='PAPER_ENTRY_READY').slice(0,10)) console.log(`ENTRY_CANDIDATE ${x.symbol} score=${x.score} sec=${x.securityDecision} holder=${x.holderClusterDecision} sell=${x.sellRoute} persist=${x.persistenceDecision||'-'} streak=${x.consecutiveEligible||0}`);
}
if(v){console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${Number(v.completedLifecycleTrades||0)} MIN=${v.minCompletedLifecycles||20}`); console.log(`VALIDATION_TOTAL_TRADES=${Number(v.totalTrades||v.trades||0)} OPEN=${Number(v.openPositions||0)}`)}
if(s)console.log(`STRESS=${s.status} FAIL=${Number(s.fail||0)}`);
if(g)console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
NODE

echo '=== PAPER DATA FILES ==='
find "$D" -maxdepth 1 -type f -printf '%f %s bytes %TY-%Tm-%TdT%TH:%TM:%TSZ\n' 2>/dev/null | sort | tail -n 30 || true

echo '=== RECENT PAPER EVENTS ==='
for f in "$D"/*.jsonl; do
  [ -f "$f" ] || continue
  echo "FILE=$(basename "$f") LINES=$(wc -l < "$f")"
  tail -n 8 "$f" | sed -E 's/(privateKey|secret|keypair|seed|mnemonic)"?:"[^"]+"/\1":"REDACTED"/Ig' || true
done

echo '=== RECENT SERVICE LOG ENTRY EVENTS ==='
journalctl -u meme-alpha-paper.service --since '90 minutes ago' --no-pager 2>/dev/null | grep -E 'PAPER_(BUY|SELL|ENTRY|EXIT)|ENTRY_READY|PROBE|POSITION|LIFECYCLE' | tail -n 80 || true

echo V231_PROGRESS_DIAGNOSTIC_PASS
