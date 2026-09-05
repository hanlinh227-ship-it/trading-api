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
# Keyless Jupiter access is rate limited; serialize all Jupiter calls from scanner.
if 'JUPITER_MIN_INTERVAL_MS = 2200' not in s:
    marker='''function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
'''
    insert='''function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

const JUPITER_MIN_INTERVAL_MS = 2200;
let lastJupiterRequestAt = 0;
async function paceJupiter() {
  const wait = Math.max(0, JUPITER_MIN_INTERVAL_MS - (Date.now() - lastJupiterRequestAt));
  if (wait > 0) await sleep(wait);
  lastJupiterRequestAt = Date.now();
}
'''
    if marker not in s:raise SystemExit('SLEEP_MARKER_NOT_FOUND')
    s=s.replace(marker,insert,1)
# getJSON is used for Jupiter token discovery; pace immediately before each network attempt.
needle='''      const r = await fetch(url, {
        headers: { accept: "application/json" },'''
repl='''      if (String(url).startsWith(String(cfg.jupiter))) await paceJupiter();
      const r = await fetch(url, {
        headers: { accept: "application/json" },'''
if needle in s:s=s.replace(needle,repl,1)
elif 'startsWith(String(cfg.jupiter))) await paceJupiter()' not in s:raise SystemExit('GETJSON_FETCH_PATTERN_NOT_FOUND')
# Old inter-source 500ms delay is redundant once global Jupiter pacing is active.
s=s.replace('if (i < ENDPOINTS.length - 1) await sleep(500);','if (i < ENDPOINTS.length - 1) await sleep(50);',1)
# Pace order requests too, including retries.
needle2='''        const r = await fetch(url, { signal: AbortSignal.timeout(10000) });'''
repl2='''        await paceJupiter();
        const r = await fetch(url, { signal: AbortSignal.timeout(10000) });'''
if needle2 in s:s=s.replace(needle2,repl2,1)
elif 'await paceJupiter();\n        const r = await fetch(url' not in s:raise SystemExit('SELLABILITY_FETCH_PATTERN_NOT_FOUND')
# Retry after a real rate-limit window, not 700ms.
s=s.replace('await new Promise(x=>setTimeout(x,700)); continue;','await new Promise(x=>setTimeout(x,2200)); continue;')
p.write_text(s)
PY
node --check src/scanner.js

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js');s=p.read_text()
# Preserve sellability tri-state in sanitized telemetry while retaining strict true-only entry gates.
s=s.replace('sellRoute:c.sellRoute===true,','sellRoute:c.sellRoute===true?true:(c.sellRoute===false?false:null),',1)
for oldv in ["version:'2.2.4'","version:'2.2.3'","version:'2.2.2'"]:
    if oldv in s:s=s.replace(oldv,"version:'2.2.7'",1);break
if "version:'2.2.7'" not in s:raise SystemExit('SAFE_EXPORT_VERSION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/safe-signal-export.js

sudo -n /bin/systemctl restart meme-alpha-paper.service
# Allow at least two paced cycles to complete without issuing any extra Jupiter calls.
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
