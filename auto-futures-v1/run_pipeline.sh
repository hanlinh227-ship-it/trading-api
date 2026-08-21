#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/trading/trading-api"
cd "$ROOT"

if [[ -f /opt/trading/.env.ai ]]; then set -a; source /opt/trading/.env.ai; set +a; fi
if [[ -f /opt/trading/.env.binance ]]; then set -a; source /opt/trading/.env.binance; set +a; fi

if [[ "${BINANCE_LIVE_TRADING:-false}" != "false" ]]; then
  echo "SAFETY BLOCK: adaptive PAPER pipeline requires BINANCE_LIVE_TRADING=false"
  exit 10
fi

echo
echo "========================================"
echo "AUTO FUTURES V5 — MTF ADAPTIVE SCALP PAPER"
echo "24/7 | NO DAILY TRADE LIMIT | NO DAILY/MAX LOSS CAP"
echo "8-TIMEFRAME ENTRY STANDARD + BOUNDED LEARNING"
echo "PER-TRADE STRUCTURAL/VOLATILITY STOP REQUIRED"
echo "========================================"

echo; echo "=== 1/7 CONTINUOUS LEARNING POLICY ==="
python3 auto-futures-v1/learning/continuous_learner.py

echo; echo "=== 2/7 LIQUID FUTURES + DEEP MTF SCANNER ==="
python3 auto-futures-v1/paper_trader.py

echo; echo "=== 3/7 THREE SPECIALIZED AI REVIEWERS ==="
python3 auto-futures-v1/ai/consensus.py

echo; echo "=== 4/7 ADAPTIVE PER-TRADE RISK ==="
python3 auto-futures-v1/risk/risk_engine.py

echo; echo "=== 5/7 PAPER EXECUTOR ==="
python3 auto-futures-v1/execution/paper_executor.py

echo; echo "=== 6/7 POSITION MANAGER ==="
python3 auto-futures-v1/position/position_manager.py

echo; echo "=== 7/7 RESEARCH JOURNAL ==="
python3 auto-futures-v1/research/learning_engine.py

echo
echo "========================================"
echo "PIPELINE COMPLETE"
echo "V5 MTF ADAPTIVE PAPER MODE"
echo "NO REAL BINANCE ORDER WAS SENT"
echo "========================================"
