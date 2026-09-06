#!/bin/bash
set -u
cd /opt/meme-alpha/app || exit 1

# v1.1.2 adaptive cadence:
# - full discovery remains rate-limit aware; never tighter than 20s between full cycles
# - active positions receive ~5s mark/exit checks
# - no-position periods avoid pointless Dex calls
# - degraded source health automatically backs off
TURBO_FULL_GAP_SEC=12
HEALTHY_FULL_GAP_SEC=15
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
  const base=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;
  const turbo=base && Number(h.successfulSources)>=4 && Number(h.failedSources||0)===0;
  console.log(turbo?'TURBO':(base?'HEALTHY':'DEGRADED'));
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
  if [ "$PROFILE" = "TURBO" ]; then
    GAP="$TURBO_FULL_GAP_SEC"
  elif [ "$PROFILE" = "HEALTHY" ]; then
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
