#!/usr/bin/env bash

set -u

ROOT="/opt/trading/trading-api"
LOCK="/tmp/auto-futures-scan.lock"
LOG="$ROOT/auto-futures-v1/logs/scan_service.log"

cd "$ROOT"

exec 9>"$LOCK"

if ! flock -n 9; then
    echo "$(date -u -Is) SCAN_SKIPPED previous scan still running" >> "$LOG"
    exit 0
fi

if [[ -f /opt/trading/.env.ai ]]; then
    set -a
    source /opt/trading/.env.ai
    set +a
fi

if [[ -f /opt/trading/.env.binance ]]; then
    set -a
    source /opt/trading/.env.binance
    set +a
fi

# HARD SAFETY
if [[ "${BINANCE_LIVE_TRADING:-false}" != "false" ]]; then
    echo "$(date -u -Is) SAFETY_BLOCK LIVE_TRADING_NOT_FALSE" >> "$LOG"
    exit 10
fi

echo >> "$LOG"
echo "====================================================" >> "$LOG"
echo "$(date -u -Is) START 3-AI PAPER SCAN" >> "$LOG"
echo "====================================================" >> "$LOG"

timeout 600 \
    "$ROOT/auto-futures-v1/run_pipeline.sh" \
    >> "$LOG" 2>&1

RC=$?

echo "$(date -u -Is) END SCAN rc=$RC" >> "$LOG"

exit "$RC"
