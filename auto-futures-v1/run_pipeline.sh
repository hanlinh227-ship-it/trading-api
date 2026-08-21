#!/usr/bin/env bash

set -euo pipefail

ROOT="/opt/trading/trading-api"

cd "$ROOT"

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


if [[ "${BINANCE_LIVE_TRADING:-false}" != "false" ]]; then

    echo "SAFETY BLOCK:"
    echo "BINANCE_LIVE_TRADING must remain false."

    exit 10
fi


echo
echo "========================================"
echo "AUTO FUTURES — 3 AI PAPER PIPELINE"
echo "========================================"


echo
echo "=== 1/5 MARKET SCANNER ==="

python3 \
auto-futures-v1/paper_trader.py


echo
echo "=== 2/5 THREE AI CONSENSUS ==="

python3 \
auto-futures-v1/ai/consensus.py


echo
echo "=== 3/5 RISK ENGINE ==="

python3 \
auto-futures-v1/risk/risk_engine.py


echo
echo "=== 4/5 PAPER EXECUTOR ==="

python3 \
auto-futures-v1/execution/paper_executor.py


echo
echo "=== 5/5 POSITION MANAGER ==="

python3 \
auto-futures-v1/position/position_manager.py


echo
echo "========================================"
echo "PIPELINE COMPLETE"
echo "PAPER MODE"
echo "NO REAL BINANCE ORDER WAS SENT"
echo "========================================"
