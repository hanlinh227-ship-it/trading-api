#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SERVICE=meme-alpha-paper.service
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v112-$STAMP

rollback(){
  rc=$?
  echo "ROLLBACK rc=$rc"
  if [ -f "$BACKUP/run-paper.sh" ]; then
    cp -f "$BACKUP/run-paper.sh" "$APP/run-paper.sh"
    chown meme-alpha:meme-alpha "$APP/run-paper.sh" || true
    chmod +x "$APP/run-paper.sh" || true
  fi
  systemctl restart "$SERVICE" || true
  exit "$rc"
}
trap rollback ERR

cd "$APP"
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('CONFIG_SCANNER_INTERVAL_MS='+c.scannerIntervalMs);
NODE

mkdir -p "$BACKUP"
cp -a run-paper.sh "$BACKUP/run-paper.sh"

systemctl stop "$SERVICE"

cat > run-paper.sh <<'SH'
#!/bin/bash
set -u
cd /opt/meme-alpha/app || exit 1

# v1.1.2 adaptive cadence:
# - full discovery remains rate-limit aware; never tighter than 20s between full cycles
# - active positions receive ~5s mark/exit checks
# - no-position periods avoid pointless Dex calls
# - degraded source health automatically backs off
HEALTHY_FULL_GAP_SEC=20
DEGRADED_FULL_GAP_SEC=45
ACTIVE_POSITION_TICK_SEC=5
IDLE_CHECK_SEC=5
FAILURE_BACKOFF_SEC=30

open_positions_count() {
  /usr/bin/node - <<'NODE' 2>/dev/null
const fs=require('fs');
try {
  const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
  console.log(Array.isArray(s.openPositions)?s.openPositions.length:0);
} catch { console.log(0); }
NODE
}

source_profile() {
  /usr/bin/node - <<'NODE' 2>/dev/null
const fs=require('fs');
try {
  const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
  const age=h.checkedAt ? (Date.now()-new Date(h.checkedAt).getTime())/1000 : Infinity;
  const ok=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;
  console.log(ok?'HEALTHY':'DEGRADED');
} catch { console.log('DEGRADED'); }
NODE
}

while true; do
  echo
  echo "=========================================="
  echo "MEME ALPHA FULL CYCLE $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "=========================================="

  FULL_START=$(date +%s)
  /usr/bin/npm run cycle5
  rc=$?

  if [ "$rc" -ne 0 ]; then
    echo "FULL_CYCLE_FAILED rc=$rc"
    echo "ADAPTIVE_BACKOFF=${FAILURE_BACKOFF_SEC}s"
    sleep "$FAILURE_BACKOFF_SEC"
    continue
  fi

  echo "FULL_CYCLE_COMPLETE"

  PROFILE=$(source_profile)
  if [ "$PROFILE" = "HEALTHY" ]; then
    GAP="$HEALTHY_FULL_GAP_SEC"
  else
    GAP="$DEGRADED_FULL_GAP_SEC"
  fi
  echo "ADAPTIVE_SOURCE_PROFILE=$PROFILE FULL_GAP=${GAP}s"

  WAIT_START=$(date +%s)
  while true; do
    NOW=$(date +%s)
    ELAPSED=$((NOW-WAIT_START))
    if [ "$ELAPSED" -ge "$GAP" ]; then
      break
    fi

    POS=$(open_positions_count)
    if [ "$POS" -gt 0 ]; then
      REM=$((GAP-ELAPSED))
      SLEEP_SEC="$ACTIVE_POSITION_TICK_SEC"
      if [ "$REM" -lt "$SLEEP_SEC" ]; then SLEEP_SEC="$REM"; fi
      [ "$SLEEP_SEC" -gt 0 ] && sleep "$SLEEP_SEC"
      echo "FAST_POSITION_TICK $(date -u +"%Y-%m-%dT%H:%M:%SZ") positions=$POS target=${ACTIVE_POSITION_TICK_SEC}s"
      MEME_ALPHA_MANAGE_ONLY=1 /usr/bin/node src/position.js || echo "FAST_POSITION_TICK_FAILED"
    else
      REM=$((GAP-ELAPSED))
      SLEEP_SEC="$IDLE_CHECK_SEC"
      if [ "$REM" -lt "$SLEEP_SEC" ]; then SLEEP_SEC="$REM"; fi
      [ "$SLEEP_SEC" -gt 0 ] && sleep "$SLEEP_SEC"
      echo "FAST_IDLE_SKIP $(date -u +"%Y-%m-%dT%H:%M:%SZ") positions=0"
    fi
  done

done
SH

chown meme-alpha:meme-alpha run-paper.sh
chmod +x run-paper.sh
bash -n run-paper.sh

echo '=== STATIC ASSERT ==='
grep -nE 'HEALTHY_FULL_GAP_SEC=20|DEGRADED_FULL_GAP_SEC=45|ACTIVE_POSITION_TICK_SEC=5|FAST_POSITION_TICK|FAST_IDLE_SKIP|ADAPTIVE_SOURCE_PROFILE|ADAPTIVE_BACKOFF' run-paper.sh

# Direct manage-only smoke test: it must stay PAPER and must not create a BUY.
BEFORE_BUYS=$(node - <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));console.log((s.trades||[]).filter(x=>x.type==='PAPER_BUY_PROBE').length);
NODE
)
MEME_ALPHA_MANAGE_ONLY=1 node src/position.js
AFTER_BUYS=$(node - <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));console.log((s.trades||[]).filter(x=>x.type==='PAPER_BUY_PROBE').length);
NODE
)
if [ "$BEFORE_BUYS" != "$AFTER_BUYS" ]; then
  echo "MANAGE_ONLY_BUY_VIOLATION before=$BEFORE_BUYS after=$AFTER_BUYS"
  exit 1
fi
echo "MANAGE_ONLY_NO_BUY_PASS count=$AFTER_BUYS"

systemctl start "$SERVICE"
sleep 75

echo '=== SERVICE ==='
systemctl --no-pager is-active "$SERVICE"
systemctl --no-pager is-enabled "$SERVICE"

echo '=== ADAPTIVE RECENT LOG ==='
tail -260 /var/log/meme-alpha/paper.log | grep -E 'FULL_CYCLE_COMPLETE|FULL_CYCLE_FAILED|ADAPTIVE_SOURCE_PROFILE|ADAPTIVE_BACKOFF|FAST_POSITION_TICK|FAST_IDLE_SKIP|FAST_MANAGE_STATUS|ORCHESTRATION=MARK_THEN_RISK_THEN_ENTRY|HTTP 429|HTTP429|JUPITER_ORDER_HTTP_429' || true

node - <<'NODE'
import fs from 'node:fs';
const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
const loop=fs.readFileSync('/opt/meme-alpha/app/run-paper.sh','utf8');
if(cfg.mode!=='PAPER') throw new Error('MODE_CHANGED');
for(const marker of ['HEALTHY_FULL_GAP_SEC=20','DEGRADED_FULL_GAP_SEC=45','ACTIVE_POSITION_TICK_SEC=5','MEME_ALPHA_MANAGE_ONLY=1']) if(!loop.includes(marker)) throw new Error('LOOP_MARKER_MISSING_'+marker);
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
console.log('SOURCE_STATUS='+h.status);
console.log('SOURCE_SUCCESS='+h.successfulSources);
console.log('SOURCE_FAILED='+h.failedSources);
console.log('USING_CACHE='+h.usingCache);
console.log('ALLOW_NEW_ENTRIES='+h.allowNewEntries);
console.log('ACTIVE_REACTION_TARGET=5s');
console.log('HEALTHY_FULL_SCAN_GAP=20s');
console.log('DEGRADED_FULL_SCAN_GAP=45s');
console.log('V112_INVARIANT_PASS');
NODE

free -h
uptime
echo "V112_DEPLOY_COMPLETE"
echo "BACKUP=$BACKUP"
trap - ERR
