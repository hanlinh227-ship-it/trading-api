#!/usr/bin/env bash
set -u
ROOT="/opt/trading/trading-api"
LOG="$ROOT/auto-futures-v1/logs/position_service.log"
cd "$ROOT"
if [[ -f /opt/trading/.env.binance ]]; then set -a; source /opt/trading/.env.binance; set +a; fi

# This daemon manages research/paper state continuously. Real-order execution remains separately guarded.
while true; do
    python3 "$ROOT/auto-futures-v1/position/ai_position_guardian.py" >> "$LOG" 2>&1 || true
    python3 "$ROOT/auto-futures-v1/position/position_manager.py" >> "$LOG" 2>&1 || true
    sleep 5
done
