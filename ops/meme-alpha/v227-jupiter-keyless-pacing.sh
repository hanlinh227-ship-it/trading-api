#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.2.7 JUPITER KEYLESS PACING ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE
B="code-backups/v227-$(date -u +%Y%m%d-%H%M%S)";mkdir -p "$B";cp -a src/scanner.js src/safe-signal-export.js "$B"/

python3 - <<'PY'
from pathlib import Path
p=Path('src/scanner.js');s=p.read_text()
if 'JUPITER_MIN_INTERVAL_MS = 2200' not in s:
    marker='async function getJSON(url) {'
    insert='''const JUPITER_MIN_INTERVAL_MS = 2200;
let lastJupiterRequestAt = 0;
async function paceJupiter() {
  const wait = Math.max(0, JUPITER_MIN_INTERVAL_MS - (Date.now() - lastJupiterRequestAt));
  if (wait > 0) await new Promise(resolve => setTimeout(resolve, wait));
  lastJupiterRequestAt = Date.now();
}

async function getJSON(url) {'''
    if marker not in s:raise SystemExit('GETJSON_MARKER_NOT_FOUND')
    s=s.replace(marker,insert,1)
# Pace each discovery request at function entry. Retry sleeps below are also lengthened.
marker2='async function getJSON(url) {'
entry='''async function getJSON(url) {
  if (String(url).startsWith(String(cfg.jupiter))) await paceJupiter();'''
if entry not in s:
    if marker2 not in s:raise SystemExit('GETJSON_ENTRY_NOT_FOUND')
    s=s.replace(marker2,entry,1)
# Pace every sellability attempt. This is deliberately true-only; transient failure remains REVIEW.
loop='for (let attempt=0; attempt<2; attempt++) {'
loop2='''for (let attempt=0; attempt<2; attempt++) {
      await paceJupiter();'''
idx=s.find('async function sellability(candidate) {')
if idx<0:raise SystemExit('SELLABILITY_NOT_FOUND')
pre=s[:idx];tail=s[idx:]
if loop2 not in tail:
    if loop not in tail:raise SystemExit('SELLABILITY_LOOP_NOT_FOUND')
    tail=tail.replace(loop,loop2,1)
s=pre+tail
# Reduce redundant source gap; global pace is authoritative.
s=s.replace('if (i < ENDPOINTS.length - 1) await sleep(500);','if (i < ENDPOINTS.length - 1) await sleep(50);',1)
# Make all known transient waits at least one keyless interval.
s=s.replace('await sleep(1500);','await sleep(2200);')
s=s.replace('await new Promise(x=>setTimeout(x,700));','await new Promise(x=>setTimeout(x,2200));')
p.write_text(s)
PY
node --check src/scanner.js

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js');s=p.read_text()
if 'sellRoute:c.sellRoute===true,' in s:s=s.replace('sellRoute:c.sellRoute===true,','sellRoute:c.sellRoute===true?true:(c.sellRoute===false?false:null),',1)
for oldv in ["version:'2.2.4'","version:'2.2.3'","version:'2.2.2'"]:
    if oldv in s:s=s.replace(oldv,"version:'2.2.7'",1);break
if "version:'2.2.7'" not in s:raise SystemExit('SAFE_EXPORT_VERSION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/safe-signal-export.js

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 210
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
! systemctl is-active --quiet meme-alpha-micro-live.service

node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));const sig=read('signal-snapshot.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json');const cs=sig.candidates||[],n=f=>cs.filter(f).length;
console.log(`SIGNAL_VERSION=${sig.version}`);console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAIL=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`CANDIDATES=${cs.length} MEME=${n(x=>x.universeClass==='MEME_CONFIRMED')} SELL_TRUE=${n(x=>x.sellRoute===true)} SELL_FALSE=${n(x=>x.sellRoute===false)} SELL_UNKNOWN=${n(x=>x.sellRoute==null)} QUOTE_429=${n(x=>String(x.sellQuoteError||'').includes('429'))}`);
console.log(`SECURITY_PASS=${n(x=>x.securityDecision==='PASS')} HOLDER_PASS=${n(x=>x.holderClusterDecision==='PASS')} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);
for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,12))console.log(`MEME ${x.symbol} score=${x.score} sec=${x.securityDecision} holder=${x.holderClusterDecision} decision=${x.decision} sell=${x.sellRoute} http=${x.sellQuoteHttp} err=${x.sellQuoteError||'-'} persist=${x.persistenceDecision||'-'} streak=${x.consecutiveEligible||0}`);
console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${Number(v.completedLifecycleTrades||0)} STRESS=${s.status}`);console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
if(sig.version!=='2.2.7')throw new Error('SIGNAL_VERSION');if(sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SOURCE_HEALTH');if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');console.log('V227_JUPITER_KEYLESS_PACING_PASS');
NODE

grep -n 'JUPITER_MIN_INTERVAL_MS' src/scanner.js | head -n 3
echo MICRO_EXECUTOR_ACTIVE=FALSE
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
