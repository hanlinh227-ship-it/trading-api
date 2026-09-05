#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LOG=/var/log/meme-alpha/paper.log
cd "$APP"

echo '=== MEME ALPHA v1.1.2 ADAPTIVE CADENCE SOAK ==='
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

START=$(wc -l < "$LOG")
echo "SOAK_START=$(date -u +%Y-%m-%dT%H:%M:%SZ) line=$START"
sleep 150
END=$(wc -l < "$LOG")
TMP=$(mktemp)
sed -n "$((START+1)),${END}p" "$LOG" > "$TMP"

FULL=$(grep -c 'FULL_CYCLE_COMPLETE' "$TMP" || true)
FAILED=$(grep -cE 'FULL_CYCLE_FAILED|FAST_POSITION_TICK_FAILED|CYCLE_FAILED' "$TMP" || true)
R429=$(grep -cE 'HTTP 429|HTTP429|JUPITER_ORDER_HTTP_429' "$TMP" || true)
HEALTHY=$(grep -c 'ADAPTIVE_SOURCE_PROFILE=HEALTHY' "$TMP" || true)
DEGRADED=$(grep -c 'ADAPTIVE_SOURCE_PROFILE=DEGRADED' "$TMP" || true)
FAST=$(grep -c 'FAST_POSITION_TICK ' "$TMP" || true)
IDLE=$(grep -c 'FAST_IDLE_SKIP ' "$TMP" || true)
ENTRYFAIL=$(grep -c 'ENTRY_FAIL ' "$TMP" || true)
EXITFAIL=$(grep -c 'EXIT_QUOTE_FAIL ' "$TMP" || true)

echo "FULL_CYCLES=$FULL"
echo "HEALTHY_PROFILES=$HEALTHY"
echo "DEGRADED_PROFILES=$DEGRADED"
echo "FAST_POSITION_TICKS=$FAST"
echo "IDLE_SKIPS=$IDLE"
echo "ENTRY_FAIL=$ENTRYFAIL"
echo "EXIT_QUOTE_FAIL=$EXITFAIL"
echo "HTTP429=$R429"
echo "CYCLE_FAILURES=$FAILED"

if [ "$FULL" -lt 3 ]; then echo 'SOAK_TOO_FEW_FULL_CYCLES'; exit 1; fi
if [ "$FAILED" -ne 0 ]; then echo 'SOAK_CYCLE_FAILURE'; exit 1; fi
if [ "$R429" -ne 0 ]; then echo 'SOAK_RATE_LIMIT_FAILURE'; exit 1; fi

echo '=== CURRENT HEALTH ==='
cat /var/lib/meme-alpha/data/paper/scanner-source-health.json

node - <<'NODE'
import fs from 'node:fs';
const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
const r=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/risk-state.json','utf8'));
if(h.status!=='HEALTHY' || h.allowNewEntries!==true || h.usingCache===true || Number(h.failedSources)!==0) throw new Error('END_SOURCE_HEALTH_BAD');
if(r.version!=='1.1') throw new Error('RISK_VERSION_BAD');
console.log('SOURCE_HEALTH_FINAL=PASS');
console.log('RISK_VERSION=1.1');
console.log('OPEN_POSITIONS='+(s.openPositions||[]).length);
console.log('EQUITY_SOL='+Number(s.equitySol||0).toFixed(6));
NODE

systemctl --no-pager is-active meme-alpha-paper.service
systemctl --no-pager is-enabled meme-alpha-paper.service
free -h
uptime
rm -f "$TMP"
echo 'V112_SOAK_PASS'
