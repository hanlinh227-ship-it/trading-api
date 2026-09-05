#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.2.5 QUOTE-PRESSURE ADAPTIVE CADENCE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE
B="code-backups/v225-$(date -u +%Y%m%d-%H%M%S)";mkdir -p "$B";cp -a run-paper.sh "$B"/

python3 - <<'PY'
from pathlib import Path
p=Path('run-paper.sh');s=p.read_text()
if 'QUOTE_BACKOFF_FULL_GAP_SEC=30' not in s:
    needle='TURBO_FULL_GAP_SEC=12\nHEALTHY_FULL_GAP_SEC=15'
    repl='QUOTE_BACKOFF_FULL_GAP_SEC=30\nTURBO_FULL_GAP_SEC=12\nHEALTHY_FULL_GAP_SEC=15'
    if needle not in s:raise SystemExit('GAP_CONSTANT_PATTERN_NOT_FOUND')
    s=s.replace(needle,repl,1)
old="""  const base=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;
  const turbo=base && Number(h.successfulSources)>=4 && Number(h.failedSources||0)===0;
  console.log(turbo?'TURBO':(base?'HEALTHY':'DEGRADED'));"""
new="""  const base=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;
  let quotePressure=0;
  try {
    const q=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-latest.json','utf8'));
    quotePressure=(q.candidates||[]).filter(c=>String(c.sellQuoteError||'').includes('429')||String(c.sellQuoteError||'').includes('TRANSIENT_HTTP_429')).length;
  } catch {}
  const turbo=base && Number(h.successfulSources)>=4 && Number(h.failedSources||0)===0 && quotePressure===0;
  console.log(quotePressure>0?'QUOTE_BACKOFF':(turbo?'TURBO':(base?'HEALTHY':'DEGRADED')));"""
if old in s:s=s.replace(old,new,1)
elif "console.log(quotePressure>0?'QUOTE_BACKOFF'" not in s:raise SystemExit('PROFILE_PATTERN_NOT_FOUND')
old2="""  if [ \"$PROFILE\" = \"TURBO\" ]; then
    GAP=\"$TURBO_FULL_GAP_SEC\"
  elif [ \"$PROFILE\" = \"HEALTHY\" ]; then"""
new2="""  if [ \"$PROFILE\" = \"QUOTE_BACKOFF\" ]; then
    GAP=\"$QUOTE_BACKOFF_FULL_GAP_SEC\"
  elif [ \"$PROFILE\" = \"TURBO\" ]; then
    GAP=\"$TURBO_FULL_GAP_SEC\"
  elif [ \"$PROFILE\" = \"HEALTHY\" ]; then"""
if old2 in s:s=s.replace(old2,new2,1)
elif 'GAP="$QUOTE_BACKOFF_FULL_GAP_SEC"' not in s:raise SystemExit('GAP_BRANCH_PATTERN_NOT_FOUND')
p.write_text(s)
PY
bash -n run-paper.sh
sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 105
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';const sig=JSON.parse(fs.readFileSync(`${R}/signal-snapshot.json`,'utf8')),g=JSON.parse(fs.readFileSync(`${R}/micro-live-gate.json`,'utf8'));console.log(`SIGNAL_VERSION=${sig.version}`);console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAIL=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);console.log(`CANDIDATES=${(sig.candidates||[]).length}`);console.log(`QUOTE_429_VISIBLE=${(sig.candidates||[]).filter(x=>String(x.sellQuoteError||'').includes('429')).length}`);console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);if(sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SOURCE_HEALTH');if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');console.log('V225_QUOTE_PRESSURE_CADENCE_PASS');
NODE
grep -E 'QUOTE_BACKOFF_FULL_GAP_SEC|TURBO_FULL_GAP_SEC|HEALTHY_FULL_GAP_SEC|DEGRADED_FULL_GAP_SEC' run-paper.sh | head -n 10
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
