#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
EXEC="$APP/src/micro-live-executor.js"
RUN="$APP/run-paper.sh"
STATE="$APP/runtime-status/micro-live-state.json"

echo '=== V344 POST ACTIVATION AUDIT ==='
[ -f "$EXEC" ] || { echo EXECUTOR_MISSING; exit 1; }
[ -f "$RUN" ] || { echo RUN_PAPER_MISSING; exit 1; }

sha256sum "$EXEC"

grep -q 'MICRO_LIVE_EXECUTOR_V342_CAPITAL_UTILIZATION' "$EXEC" && echo V342_EXECUTOR_MARKER=TRUE || echo V342_EXECUTOR_MARKER=FALSE
grep -q 'CAPITAL_UTILIZATION_FIRST' "$EXEC" && echo CAPITAL_UTILIZATION_FIRST=TRUE || echo CAPITAL_UTILIZATION_FIRST=FALSE
grep -q 'FREE_CAPITAL_BOOSTS_NEW_BUYS' "$EXEC" && echo FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE || echo FREE_CAPITAL_BOOSTS_NEW_BUYS=FALSE
grep -q 'MULTI_POSITION_NO_HARD_COUNT_LIMIT' "$EXEC" && echo MULTI_POSITION_NO_HARD_COUNT_LIMIT=TRUE || echo MULTI_POSITION_NO_HARD_COUNT_LIMIT=FALSE

grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=60' "$RUN" && echo V341_SIGNAL_TTL_60=TRUE || echo V341_SIGNAL_TTL_60=FALSE
grep -q 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH' "$RUN" && echo V341_CONTINUITY_MARKER=TRUE || echo V341_CONTINUITY_MARKER=FALSE
grep -q "close_entry_gate 'FULL_CYCLE_FAILED'" "$RUN" && echo FULL_CYCLE_FAIL_CLOSE=TRUE || echo FULL_CYCLE_FAIL_CLOSE=FALSE
! grep -q '/usr/bin/node src/position.js' "$RUN" && echo PAPER_EXECUTION_DISABLED=TRUE || echo PAPER_EXECUTION_DISABLED=FALSE

echo EXECUTOR_PROCESSES=$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)
echo SIGNER_PROCESSES=$(pgrep -fc '/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py' || true)
echo PAPER_SERVICE=$(systemctl is-active meme-alpha-paper.service 2>/dev/null || true)
echo MICRO_LIVE_SERVICE=$(systemctl is-active meme-alpha-micro-live.service 2>/dev/null || true)

if [ -f "$STATE" ]; then
  node - "$STATE" <<'NODE'
const fs=require('fs'); const p=process.argv[2];
try { const s=JSON.parse(fs.readFileSync(p,'utf8')); const a=Array.isArray(s.positions)?s.positions:[]; console.log('STATE_POSITIONS='+a.length); console.log('STATE_VERSION='+(s.version||'')); } catch(e){ console.log('STATE_READ_ERROR='+e.message); }
NODE
else
  echo STATE_MISSING=TRUE
fi

if grep -q 'MICRO_LIVE_EXECUTOR_V342_CAPITAL_UTILIZATION' "$EXEC" && \
   grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=60' "$RUN" && \
   grep -q 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH' "$RUN" && \
   grep -q "close_entry_gate 'FULL_CYCLE_FAILED'" "$RUN" && \
   [ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ] && \
   [ "$(pgrep -fc '/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py' || true)" -eq 1 ]; then
  echo V344_POST_ACTIVATION_AUDIT=PASS
else
  echo V344_POST_ACTIVATION_AUDIT=FAIL
  exit 1
fi
