#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/trading/trading-api"
cd "$ROOT"

if [[ -f /opt/trading/.env.ai ]]; then set -a; source /opt/trading/.env.ai; set +a; fi
if [[ -f /opt/trading/.env.binance ]]; then set -a; source /opt/trading/.env.binance; set +a; fi
if [[ -f /opt/trading/.env.telegram ]]; then set -a; source /opt/trading/.env.telegram; set +a; fi

echo
echo "========================================"
echo "AUTO FUTURES V6 — MTF ADAPTIVE SCALP"
echo "24/7 | EXISTING HUB PER-TRADE CONFIRMATION"
echo "========================================"

echo; echo "=== 1/9 CONTINUOUS LEARNING POLICY ==="
python3 auto-futures-v1/learning/continuous_learner.py

echo; echo "=== 2/9 LIQUID FUTURES + DEEP MTF SCANNER ==="
python3 auto-futures-v1/paper_trader.py

echo; echo "=== 3/9 THREE SPECIALIZED AI REVIEWERS ==="
python3 auto-futures-v1/ai/consensus.py

echo; echo "=== 4/9 ADAPTIVE PER-TRADE RISK ==="
python3 auto-futures-v1/risk/risk_engine.py

echo; echo "=== 5/9 EXECUTION GUARD ==="
python3 auto-futures-v1/execution/execution_guard.py

echo; echo "=== 6/9 PAPER EXECUTOR ==="
python3 auto-futures-v1/execution/paper_executor.py

echo; echo "=== 7/9 POSITION MANAGER ==="
python3 auto-futures-v1/position/position_manager.py

echo; echo "=== 8/9 RESEARCH JOURNAL ==="
python3 auto-futures-v1/research/learning_engine.py

echo; echo "=== 9/9 HUB APPROVAL QUEUE ==="
python3 auto-futures-v1/execution/approval_queue.py

echo
echo "========================================"
echo "PIPELINE COMPLETE"
echo "V6 MTF ADAPTIVE RESEARCH COMPLETE"
echo "LIVE ORDER REQUIRES EXISTING HUB CONFIRMATION"
echo "NO REAL BINANCE ORDER WAS SENT"
echo "========================================"
