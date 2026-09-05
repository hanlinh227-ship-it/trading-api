#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SCANNER="$APP/src/scanner.js"
SIG="$APP/runtime-status/signal-snapshot.json"
GATE="$APP/runtime-status/micro-live-gate.json"
SERVICE=meme-alpha-paper.service
TARGET_CHECKS=3
cd "$APP"

echo '=== V307 R2 SELL-ROUTE BUDGET AUTOTUNE ==='
[ -r "$SCANNER" ] || { echo 'SCANNER_NOT_READABLE'; exit 2; }
[ -w "$APP/src" ] || { echo 'SRC_DIR_NOT_WRITABLE'; exit 3; }

grep -q '^const MAX_SELLABILITY_CHECKS_V216=8;$' "$SCANNER" || {
  if grep -q '^const MAX_SELLABILITY_CHECKS_V216=3;' "$SCANNER"; then
    echo 'SELL_ROUTE_BUDGET_ALREADY_TUNED=TRUE'
  else
    echo 'UNKNOWN_SELL_ROUTE_BUDGET_ABORT'; exit 4
  fi
}

grep -q 'await paceJupiter();' "$SCANNER" || { echo 'JUPITER_PACING_GUARD_MISSING'; exit 5; }
grep -q 'sell.sellRoute === false' "$SCANNER" || { echo 'NO_SELL_ROUTE_FAIL_CLOSED_GUARD_MISSING'; exit 6; }
grep -q 'SELLABILITY_TEMPORARILY_UNAVAILABLE' "$SCANNER" || { echo 'TRANSIENT_FAIL_CLOSED_GUARD_MISSING'; exit 7; }

backup="$APP/runtime-status/scanner-v307-$(date -u +%Y%m%dT%H%M%SZ).js.bak"
cp -p "$SCANNER" "$backup"
echo "BACKUP=$backup"

if grep -q '^const MAX_SELLABILITY_CHECKS_V216=8;$' "$SCANNER"; then
  tmp="$APP/src/.scanner-v307.$$.js"
  python3 - "$SCANNER" "$TARGET_CHECKS" > "$tmp" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); target=sys.argv[2]
s=p.read_text()
old='const MAX_SELLABILITY_CHECKS_V216=8;'
if s.count(old)!=1: raise SystemExit('unexpected baseline count')
s=s.replace(old,f'const MAX_SELLABILITY_CHECKS_V216={target}; // V307 latency budget: verify only top opportunity candidates each cycle')
sys.stdout.write(s)
PY
  /usr/bin/node --check "$tmp"
  chmod 664 "$tmp" || true
  mv -f "$tmp" "$SCANNER"
  echo 'SCANNER_ATOMIC_REPLACE=TRUE'
fi

# Exact safety invariants after replacement.
grep -q '^const MAX_SELLABILITY_CHECKS_V216=3;' "$SCANNER"
grep -q 'await paceJupiter();' "$SCANNER"
grep -q 'sell.sellRoute === false' "$SCANNER"
grep -q 'NO_SELL_ROUTE' "$SCANNER"
grep -q 'SELLABILITY_TEMPORARILY_UNAVAILABLE' "$SCANNER"
/usr/bin/node --check "$SCANNER"
stat -c 'SCANNER owner=%U group=%G mode=%a size=%s' "$SCANNER"

echo 'SELL_ROUTE_CHECKS_PER_CYCLE_BEFORE=8'
echo 'SELL_ROUTE_CHECKS_PER_CYCLE_AFTER=3'
echo 'JUPITER_PACING_CHANGED=FALSE'
echo 'DEX_LIQUIDITY_GATE_CHANGED=FALSE'
echo 'SELL_ROUTE_REQUIREMENT_CHANGED=FALSE'
echo 'RISK_LIMITS_CHANGED=FALSE'
echo 'SECURITY_THRESHOLDS_CHANGED=FALSE'

rollback(){
  echo 'ROLLBACK_START=TRUE'
  local rt="$APP/src/.scanner-v307-rollback.$$.js"
  cp "$backup" "$rt"
  /usr/bin/node --check "$rt" || true
  chmod 664 "$rt" || true
  mv -f "$rt" "$SCANNER"
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo 'ROLLBACK_DONE=TRUE'
}

pre=$(node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(x.timestamp||x.updatedAt||x.generatedAt||''))}catch{}
NODE
)
echo "PRE_SIGNAL_STAMP=$pre"
start=$(date +%s)
if ! sudo -n /bin/systemctl restart "$SERVICE"; then rollback; echo 'PAPER_RESTART_FAILED'; exit 8; fi
sleep 2
sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null || { rollback; echo 'PAPER_NOT_ACTIVE'; exit 9; }

echo '=== LATENCY VERIFY: TWO FRESH SIGNALS ==='
last="$pre"; updates=0; first_epoch=0; second_epoch=0
for i in $(seq 1 90); do
  sleep 2
  [ -r "$SIG" ] || continue
  row=$(node - "$SIG" "$GATE" <<'NODE' 2>/dev/null || true
const fs=require('fs');
try{
 const s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 let g={};try{g=JSON.parse(fs.readFileSync(process.argv[3],'utf8'))}catch{}
 const t=String(s.timestamp||s.updatedAt||s.generatedAt||'');
 const ms=Date.parse(t); const age=Number.isFinite(ms)?Math.max(0,(Date.now()-ms)/1000):999999;
 const h=s.sourceHealth||{};
 console.log([t,age.toFixed(2),String(h.status||''),h.usingCache===true?'1':'0',g.allowed===true?'1':'0',(Array.isArray(g.reasons)?g.reasons:[]).join('+')].join('|'));
}catch{}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r stamp age source cache allowed reasons <<< "$row"
  if [ -n "$stamp" ] && [ "$stamp" != "$last" ]; then
    updates=$((updates+1)); now=$(date +%s); last="$stamp"
    echo "NEW_SIGNAL_$updates stamp=$stamp ageSec=$age source=$source cache=$cache gateAllowed=$allowed reasons=$reasons elapsed=$((now-start))s"
    if [ "$updates" -eq 1 ]; then first_epoch=$now; fi
    if [ "$updates" -eq 2 ]; then second_epoch=$now; break; fi
  fi
done

if [ "$updates" -lt 2 ]; then rollback; echo "V307_VERIFY_FAIL_UPDATES=$updates"; exit 10; fi
first_latency=$((first_epoch-start))
steady_interval=$((second_epoch-first_epoch))
echo "FIRST_FRESH_SIGNAL_LATENCY_SEC=$first_latency"
echo "STEADY_SIGNAL_INTERVAL_SEC=$steady_interval"

# Baseline observed ~75s between signal updates. Require a material improvement without weakening gates.
if [ "$first_latency" -gt 40 ] || [ "$steady_interval" -gt 35 ]; then
  rollback
  echo 'V307_LATENCY_TARGET_MISSED_ROLLBACK=TRUE'
  exit 11
fi

echo 'V307_R2_SELLROUTE_BUDGET_AUTOTUNE_PASS'
