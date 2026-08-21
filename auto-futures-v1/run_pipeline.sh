#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/trading/trading-api"
cd "$ROOT"

if [[ -f /opt/trading/.env.ai ]]; then set -a; source /opt/trading/.env.ai; set +a; fi
if [[ -f /opt/trading/.env.binance ]]; then set -a; source /opt/trading/.env.binance; set +a; fi

if [[ "${BINANCE_LIVE_TRADING:-false}" != "false" ]]; then
  echo "SAFETY BLOCK: PAPER pipeline requires BINANCE_LIVE_TRADING=false"
  exit 10
fi

echo
echo "========================================"
echo "AUTO FUTURES V4 — ADAPTIVE SCALP PAPER"
echo "24/7 | NO DAILY TRADE LIMIT | NO DAILY/MAX LOSS CAP"
echo "PER-TRADE STRUCTURAL STOP REQUIRED"
echo "========================================"

echo; echo "=== 1/6 LIQUID FUTURES SCANNER ==="
python3 auto-futures-v1/paper_trader.py

echo; echo "=== 2/6 THREE SPECIALIZED AI REVIEWERS ==="
python3 auto-futures-v1/ai/consensus.py

echo; echo "=== 3/6 ADAPTIVE PER-TRADE RISK ==="
python3 auto-futures-v1/risk/risk_engine.py

echo; echo "=== 4/6 PAPER EXECUTOR ==="
python3 auto-futures-v1/execution/paper_executor.py

echo; echo "=== 5/6 POSITION MANAGER ==="
python3 auto-futures-v1/position/position_manager.py

echo; echo "=== 6/6 LEARNING JOURNAL ==="
python3 auto-futures-v1/research/learning_engine.py

echo
echo "========================================"
echo "PIPELINE COMPLETE"
echo "PAPER MODE"
echo "NO REAL BINANCE ORDER WAS SENT"
echo "========================================"
