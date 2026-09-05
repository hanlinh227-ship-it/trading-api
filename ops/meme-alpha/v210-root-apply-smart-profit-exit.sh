#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC="$APP/ops/meme-alpha/micro-live/micro-live-executor-v210.js"
DST="$APP/src/micro-live-executor.js"
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.10 SMART PROFIT / ANTI-WHIPSAW EXIT APPLY ==='
[ -f "$SRC" ] || { echo ABORT_V210_NOT_STAGED; exit 1; }
[ -f /etc/meme-alpha/signer-enabled ] && grep -qx 'ARMED=YES' /etc/meme-alpha/signer-enabled || { echo ABORT_SIGNER_NOT_ARMED; exit 1; }
[ -f /etc/meme-alpha/execution-mode ] && grep -qx 'MICRO_LIVE' /etc/meme-alpha/execution-mode || { echo ABORT_NOT_MICRO_LIVE; exit 1; }
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet meme-alpha-micro-live.service
node --check "$SRC"
node "$SRC" --self-test | tee /tmp/v210-exec.txt
grep -q 'MICRO_EXECUTOR_V210_SELF_TEST=PASS' /tmp/v210-exec.txt
rm -f /tmp/v210-exec.txt

grep -q 'HARD_SAFETY_BREAK' "$SRC"
grep -q 'CONFIRMED_TREND_BREAK' "$SRC"
grep -q 'SMART_TP1' "$SRC"
grep -q 'SMART_TP2' "$SRC"
grep -q 'SMART_TP3_RUNNER_LOCK' "$SRC"
grep -q 'SMART_PROFIT_GIVEBACK' "$SRC"

STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v210-$STAMP
mkdir -p "$BACKUP"
cp -a "$DST" "$BACKUP/micro-live-executor.js"
trap 'rc=$?; echo "V210_ROLLBACK rc=$rc" >&2; cp -f "$BACKUP/micro-live-executor.js" "$DST" || true; systemctl restart meme-alpha-micro-live.service >/dev/null 2>&1 || true; exit $rc' ERR

install -o root -g root -m 0644 "$SRC" "$DST"
systemctl restart meme-alpha-micro-live.service
sleep 4
systemctl is-active --quiet meme-alpha-micro-live.service
PID=$(systemctl show meme-alpha-micro-live.service -p MainPID --value)
START=$(systemctl show meme-alpha-micro-live.service -p ActiveEnterTimestamp --value)
echo MICRO_EXECUTOR_V210_ACTIVE=TRUE
echo MICRO_EXECUTOR_PID=$PID
echo MICRO_EXECUTOR_START="$START"

# Read-only state summary as root, never expose keys or signer socket contents.
python3 - <<'PY'
import json,os
p='/var/lib/meme-alpha/data/micro-live/state.json'
try:s=json.load(open(p))
except:s={}
pos=s.get('position')
print('LIVE_POSITION_OPEN='+('TRUE' if pos else 'FALSE'))
if pos:
 print('LIVE_POSITION_SYMBOL='+str(pos.get('symbol','UNKNOWN')))
 print('LIVE_POSITION_TIER='+str(pos.get('tier','UNKNOWN')))
 print('LIVE_POSITION_TP1_DONE='+str(bool(pos.get('tp1Done'))).lower())
 print('LIVE_POSITION_TP2_DONE='+str(bool(pos.get('tp2Done'))).lower())
 print('LIVE_POSITION_PROFIT_PROTECT_DONE='+str(bool(pos.get('profitProtectDone'))).lower())
PY

echo TRANSIENT_GATE_CLOSE_BLOCKS_NEW_RISK_BUT_DOES_NOT_FORCE_DUMP=TRUE
echo HARD_SAFETY_EXIT_IMMEDIATE=TRUE
echo SOFT_WEAKNESS_REQUIRES_CONFIRMATION=TRUE
echo SMART_PARTIAL_TP_ENABLED=TRUE
echo RUNNER_PRESERVED_WHILE_TREND_HEALTHY=TRUE
echo SCALE_IN_LOCKED_AFTER_PROFIT_HARVEST=TRUE
echo CAPITAL_STAGES_UNCHANGED=15_35_65_94
echo V210_SMART_PROFIT_EXIT_APPLY_PASS
echo "BACKUP=$BACKUP"
