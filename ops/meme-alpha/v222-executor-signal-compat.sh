#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.2.2 EXECUTOR SIGNAL COMPAT ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER'); console.log('LIVE_EXECUTION=DISABLED');
NODE

B="code-backups/v222-$(date -u +%Y%m%d-%H%M%S)"; mkdir -p "$B"; cp -a src/safe-signal-export.js "$B"/; [ -f src/micro-live-executor.js ] && cp -a src/micro-live-executor.js "$B"/ || true

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js'); s=p.read_text()
old="sellImpactPct:Number.isFinite(Number(c.sellImpactPct))?Number(c.sellImpactPct):null,priceImpactPct:Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null"
new="sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):null,sellImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):(Number.isFinite(Number(c.sellImpactPct))?Number(c.sellImpactPct):(Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null)),priceImpactPct:Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null"
if old in s:s=s.replace(old,new,1)
elif 'sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))' not in s:raise SystemExit('SAFE_SIGNAL_IMPACT_PATTERN_NOT_FOUND')
# Never downgrade a newer exporter on rerun.
if not any(f"version:'{v}'" in s for v in ['2.2.3','2.2.4','2.2.5','2.3.0']):
    for oldv in ["version:'2.2.0'","version:'2.1.6'","version:'2.1.4'","version:'2.1.2'","version:'2.0.1'"]:
        if oldv in s:s=s.replace(oldv,"version:'2.2.2'",1);break
p.write_text(s)
PY
node --check src/safe-signal-export.js

python3 - <<'PY'
from pathlib import Path
paths=[Path('src/micro-live-executor.js'),Path('ops/security/micro-live-executor-v192.js')]
old="const impact=Number(c.sellImpactPct??c.priceImpactPct);"
new="const impact=Number(c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct);"
patched=0
for p in paths:
    if not p.exists(): continue
    s=p.read_text()
    if old in s:s=s.replace(old,new,1);p.write_text(s);patched+=1
    elif new in s:patched+=1
    else:raise SystemExit('EXECUTOR_IMPACT_PATTERN_NOT_FOUND_'+str(p))
print('EXECUTOR_COMPAT_FILES='+str(patched))
if patched<1:raise SystemExit('NO_EXECUTOR_FILE_PATCHED')
PY
node --check src/micro-live-executor.js

# Do NOT execute safe-signal-export as github-runner: it is intentionally denied
# access to private PAPER files and would overwrite the sanitized snapshot empty.
! systemctl is-active --quiet meme-alpha-micro-live.service
[ "$(systemctl is-enabled meme-alpha-micro-live.service 2>/dev/null || true)" != enabled ]
node src/micro-live-executor.js --self-test

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const src=fs.readFileSync('src/safe-signal-export.js','utf8');
const ex=fs.readFileSync('src/micro-live-executor.js','utf8');
const g=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','utf8'));
if(!src.includes('sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))'))throw new Error('EXPORT_COMPAT_MISSING');
if(!ex.includes('c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct'))throw new Error('EXECUTOR_COMPAT_MISSING');
if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');
console.log('V222_EXECUTOR_SIGNAL_COMPAT_PASS');
NODE

echo MICRO_EXECUTOR_ACTIVE=FALSE
echo NETWORK_EXECUTION=NOT_CALLED
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
