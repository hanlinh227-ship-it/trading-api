#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== V304 CYCLE5 + LIVE GATE AUDIT ==='

echo '=== LIVE GATE CONTROL ==='
GATE="$APP/runtime-status/micro-live-gate.json"
if stat -c 'GATE owner=%U group=%G mode=%a size=%s' "$GATE" 2>/dev/null; then
  [ -r "$GATE" ] && echo 'GATE_READABLE=TRUE' || echo 'GATE_READABLE=FALSE'
  [ -w "$GATE" ] && echo 'GATE_WRITABLE=TRUE' || echo 'GATE_WRITABLE=FALSE'
  if [ -r "$GATE" ]; then
    node - "$GATE" <<'NODE' || true
const fs=require('fs');
try {const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8')); const keep=['version','timestamp','updatedAt','allowed','reason','reasons','signalAgeSec','trendAgeSec','eligibleCount','sourceHealth','shadowReady','liveExecution','signerReady','policyReady']; const o={}; for(const k of keep) if(Object.prototype.hasOwnProperty.call(x,k)) o[k]=x[k]; console.log(JSON.stringify(o,null,2));} catch(e){console.log('GATE_PARSE_FAIL')}
NODE
  fi
else echo 'GATE_STAT_UNAVAILABLE'; fi

echo '=== ROOT POLICY METADATA ONLY ==='
POL=/etc/meme-alpha/micro-live-policy.json
stat -c 'POLICY owner=%U group=%G mode=%a size=%s' "$POL" 2>/dev/null || echo 'POLICY_STAT_UNAVAILABLE'
[ -r "$POL" ] && echo 'POLICY_READABLE=TRUE' || echo 'POLICY_READABLE=FALSE'
[ -w "$POL" ] && echo 'POLICY_WRITABLE=TRUE' || echo 'POLICY_WRITABLE=FALSE'

echo '=== PACKAGE CYCLE SCRIPTS ==='
node - <<'NODE' || true
const fs=require('fs'); try {const p=JSON.parse(fs.readFileSync('package.json','utf8')); const s=p.scripts||{}; for(const k of Object.keys(s).sort()) if(/cycle|scan|signal|security|holder|trend|paper|position|source/i.test(k)) console.log(`${k}=${s[k]}`);} catch(e){console.log('PACKAGE_PARSE_FAIL')}
NODE

echo '=== CURRENT PAPER LAUNCHER CADENCE ==='
grep -nE 'FULL_GAP|TICK_SEC|CHECK_SEC|BACKOFF_SEC|npm run cycle' run-paper.sh 2>/dev/null || true

echo '=== CYCLE5 REFERENCED FILES / COMMANDS ==='
cycle=$(node -e "try{const p=require('./package.json');process.stdout.write(String((p.scripts||{}).cycle5||''))}catch{}")
echo "CYCLE5=$cycle"
# List local script paths named by package script, without executing them.
printf '%s\n' "$cycle" | grep -oE '(src|scripts|ops)/[^ ;|&]+' | sort -u || true

echo '=== SCANNER NETWORK / CONCURRENCY HOTSPOTS ==='
for f in src/scanner.js src/safe-signal-export.js src/source-health.js src/security*.js src/holder*.js; do
  [ -r "$f" ] || continue
  echo "--- $f"
  grep -nEi 'Promise\.all|await .*fetch|await .*quote|jupiter|dexscreener|birdeye|helius|sleep\(|setTimeout|concurr|batch|for *\(|for .* of|writeFile|signal-snapshot' "$f" | head -220 || true
done

echo '=== PAPER LOG METADATA / RECENT CYCLE MARKERS ==='
for f in /var/log/meme-alpha/paper.log /var/log/meme-alpha/paper-error.log; do
  stat -c '%n owner=%U group=%G mode=%a size=%s' "$f" 2>/dev/null || continue
  [ -r "$f" ] || { echo "$f READABLE=FALSE"; continue; }
  echo "--- $f"
  tail -n 500 "$f" | grep -Ei 'FULL_CYCLE|cycle5|scanner|signal|source|quote|duration|elapsed|start|complete|pass|fail|error|429' | tail -180 || true
done

echo '=== RUNTIME STATUS MTIMES ==='
find runtime-status -maxdepth 1 -type f \( -name '*signal*' -o -name '*trend*' -o -name '*gate*' -o -name '*source*' -o -name '*shadow*' \) -printf '%TY-%Tm-%TdT%TH:%TM:%TS %f\n' 2>/dev/null | sort || true

echo 'V304_CYCLE5_LIVE_GATE_AUDIT_PASS'
