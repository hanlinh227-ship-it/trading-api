#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
BOT="$ROOT/auto-futures-v1"
LOCK="/tmp/auto-futures-scan.lock"
LOG="$BOT/logs/scan_service.log"
MAX_RUNTIME_SECONDS="${AUTO_FUTURES_SCAN_MAX_RUNTIME_SECONDS:-240}"

mkdir -p "$BOT/logs"
cd "$ROOT"

# Production invariant: at most ONE complete scan pipeline may exist at a time.
# systemd already avoids duplicate activation of the same service; flock is the
# second independent guard against manual starts/old timers/race conditions.
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u -Is) SCAN_SKIPPED reason=SINGLETON_LOCK_BUSY" >> "$LOG"
    exit 0
fi

if [[ -f /opt/trading/.env.ai ]]; then
    set -a; source /opt/trading/.env.ai; set +a
fi
if [[ -f /opt/trading/.env.binance ]]; then
    set -a; source /opt/trading/.env.binance; set +a
fi
if [[ -f /opt/trading/.env.telegram ]]; then
    set -a; source /opt/trading/.env.telegram; set +a
fi

# The scanner itself has NO order authority. LIVE flags are allowed here because
# live execution is gated exclusively inside live_executor.py after Hub confirm.
# Never block market scanning merely because LIVE mode is armed.

echo >> "$LOG"
echo "====================================================" >> "$LOG"
echo "$(date -u -Is) START AUTO FUTURES PRODUCTION SCAN" >> "$LOG"
echo "mode=CONFIRM_PER_TRADE live_trading=${BINANCE_LIVE_TRADING:-false} live_armed=${BINANCE_LIVE_ARMED:-false}" >> "$LOG"
echo "singleton_lock=ACQUIRED max_runtime=${MAX_RUNTIME_SECONDS}s" >> "$LOG"
echo "====================================================" >> "$LOG"

set +e
timeout --signal=TERM --kill-after=10 "${MAX_RUNTIME_SECONDS}" \
    "$BOT/run_pipeline.sh" >> "$LOG" 2>&1
RC=$?
set -e

case "$RC" in
  0)   RESULT="PASS" ;;
  124) RESULT="TIMEOUT" ;;
  137) RESULT="KILLED_AFTER_TIMEOUT" ;;
  *)   RESULT="FAIL" ;;
esac

echo "$(date -u -Is) END SCAN rc=$RC result=$RESULT" >> "$LOG"

# A timed-out/failed scan must not poison the timer. State remains fail-closed:
# approval_queue/live_executor require fresh validated state before execution.
exit 0
