#!/usr/bin/env bash

set -u

ROOT="/opt/trading/trading-api"
LOG="$ROOT/auto-futures-v1/logs/position_service.log"

cd "$ROOT"

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

while true; do

    python3 \
        "$ROOT/auto-futures-v1/position/position_manager.py" \
        >> "$LOG" 2>&1

    sleep 5

done
