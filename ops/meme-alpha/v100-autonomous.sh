#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LOG=/var/log/meme-alpha/paper.log
cd "$APP"

echo '=== MEME ALPHA v1.1.1 REACTIVE SOAK TEST ==='
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

START_LINES=$(wc -l < "$LOG")
START_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "SOAK_START=$START_TS lines=$START_LINES"
sleep 125
END_LINES=$(wc -l < "$LOG")
TMP=$(mktemp)
sed -n "$((START_LINES+1)),${END_LINES}p" "$LOG" > "$TMP"

echo '=== SOAK COUNTS ==='
echo "FAST_TICKS=$(grep -c 'FAST_POSITION_TICK=' "$TMP" || true)"
echo "FAST_MANAGE_PASS=$(grep -c 'FAST_MANAGE_STATUS=PASS' "$TMP" || true)"
echo "FULL_CYCLES=$(grep -c 'FULL_CYCLE_COMPLETE' "$TMP" || true)"
echo "ORCHESTRATED=$(grep -c 'ORCHESTRATION=MARK_THEN_RISK_THEN_ENTRY' "$TMP" || true)"
echo "POSITION_PASS=$(grep -c 'POSITION_ENGINE_STATUS=PASS' "$TMP" || true)"
echo "ENTRY_FAIL=$(grep -c 'ENTRY_FAIL ' "$TMP" || true)"
echo "EXIT_QUOTE_FAIL=$(grep -c 'EXIT_QUOTE_FAIL ' "$TMP" || true)"
echo "HTTP429=$(grep -cE 'HTTP 429|HTTP429|JUPITER_ORDER_HTTP_429' "$TMP" || true)"
echo "CYCLE_FAILED=$(grep -cE 'CYCLE_FAILED|FULL_CYCLE_FAILED|FAST_POSITION_TICK_FAILED' "$TMP" || true)"

echo '=== SOURCE HEALTH ==='
cat /var/lib/meme-alpha/data/paper/scanner-source-health.json

echo '=== STATE INVARIANTS ==='
node - <<'NODE'
import fs from 'node:fs';
const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
const r=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/risk-state.json','utf8'));
const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
const recentBuys=(s.trades||[]).filter(x=>x.type==='PAPER_BUY_PROBE').slice(-20);
const missingIds=recentBuys.filter(x=>!x.positionId).length;
const dupIds=recentBuys.length-new Set(recentBuys.map(x=>x.positionId).filter(Boolean)).size;
if(missingIds>0) throw new Error('RECENT_BUY_POSITION_ID_MISSING');
if(dupIds>0) throw new Error('RECENT_BUY_POSITION_ID_DUPLICATE');
if(h.status!=='HEALTHY' || h.allowNewEntries!==true || h.usingCache===true) throw new Error('SOURCE_HEALTH_NOT_HEALTHY');
if(r.version!=='1.1') throw new Error('RISK_VERSION_UNEXPECTED');
console.log('RECENT_BUY_POSITION_IDS=PASS count='+recentBuys.length);
console.log('SOURCE_HEALTH=HEALTHY');
console.log('RISK_VERSION=1.1');
console.log('OPEN_POSITIONS='+(s.openPositions||[]).length);
console.log('EQUITY_SOL='+Number(s.equitySol||0).toFixed(6));
NODE

echo '=== SERVICE ==='
systemctl --no-pager is-active meme-alpha-paper.service
systemctl --no-pager is-enabled meme-alpha-paper.service
free -h
uptime
rm -f "$TMP"
echo 'V111_SOAK_PASS'
