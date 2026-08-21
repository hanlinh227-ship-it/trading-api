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

while true; do
    # No AI token cost: refresh verified Binance market context with a 20s cache.
    python3 "$ROOT/auto-futures-v1/research/market_context_monitor.py" >> "$LOG" 2>&1 || true

    # Guardian uses the latest 3-AI consensus + refreshed market context.
    python3 "$ROOT/auto-futures-v1/position/ai_position_guardian.py" >> "$LOG" 2>&1 || true

    python3 "$ROOT/auto-futures-v1/position/position_manager.py" >> "$LOG" 2>&1

    sleep 5
done
