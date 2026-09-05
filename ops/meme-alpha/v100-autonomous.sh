#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LOG=/var/log/meme-alpha/paper.log
DEPLOY_CUTOFF='2026-09-05T04:45:26Z'
cd "$APP"

echo '=== MEME ALPHA v1.1.1 POST-SOAK INVARIANT RETEST ==='
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

TMP=$(mktemp)
tail -600 "$LOG" > "$TMP"
echo "FAST_TICKS_RECENT=$(grep -c 'FAST_POSITION_TICK=' "$TMP" || true)"
echo "FAST_MANAGE_PASS_RECENT=$(grep -c 'FAST_MANAGE_STATUS=PASS' "$TMP" || true)"
echo "FULL_CYCLES_RECENT=$(grep -c 'FULL_CYCLE_COMPLETE' "$TMP" || true)"
echo "ORCHESTRATED_RECENT=$(grep -c 'ORCHESTRATION=MARK_THEN_RISK_THEN_ENTRY' "$TMP" || true)"
echo "ENTRY_FAIL_RECENT=$(grep -c 'ENTRY_FAIL ' "$TMP" || true)"
echo "EXIT_QUOTE_FAIL_RECENT=$(grep -c 'EXIT_QUOTE_FAIL ' "$TMP" || true)"
echo "HTTP429_RECENT=$(grep -cE 'HTTP 429|HTTP429|JUPITER_ORDER_HTTP_429' "$TMP" || true)"
echo "CYCLE_FAILED_RECENT=$(grep -cE 'CYCLE_FAILED|FULL_CYCLE_FAILED|FAST_POSITION_TICK_FAILED' "$TMP" || true)"

echo '=== SOURCE HEALTH ==='
cat /var/lib/meme-alpha/data/paper/scanner-source-health.json

echo '=== STATE INVARIANTS ==='
node - <<'NODE'
import fs from 'node:fs';
const cutoff=new Date('2026-09-05T04:45:26Z').getTime();
const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
const r=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/risk-state.json','utf8'));
const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
const newBuys=(s.trades||[]).filter(x=>x.type==='PAPER_BUY_PROBE' && new Date(x.timestamp).getTime()>=cutoff);
const missingIds=newBuys.filter(x=>!x.positionId).length;
const ids=newBuys.map(x=>x.positionId).filter(Boolean);
const dupIds=ids.length-new Set(ids).size;
if(missingIds>0) throw new Error('POST_V111_BUY_POSITION_ID_MISSING');
if(dupIds>0) throw new Error('POST_V111_BUY_POSITION_ID_DUPLICATE');
if(h.status!=='HEALTHY' || h.allowNewEntries!==true || h.usingCache===true) throw new Error('SOURCE_HEALTH_NOT_HEALTHY');
if(r.version!=='1.1') throw new Error('RISK_VERSION_UNEXPECTED');
console.log('POST_V111_BUY_POSITION_IDS=PASS count='+newBuys.length);
console.log('LEGACY_BUYS_IGNORED='+(s.trades||[]).filter(x=>x.type==='PAPER_BUY_PROBE' && new Date(x.timestamp).getTime()<cutoff).length);
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
echo 'V111_POST_SOAK_PASS'
