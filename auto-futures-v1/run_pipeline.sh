#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/trading/trading-api"
cd "$ROOT"

if [[ -f /opt/trading/.env.ai ]]; then set -a; source /opt/trading/.env.ai; set +a; fi
if [[ -f /opt/trading/.env.binance ]]; then set -a; source /opt/trading/.env.binance; set +a; fi
if [[ -f /opt/trading/.env.telegram ]]; then set -a; source /opt/trading/.env.telegram; set +a; fi

echo
echo "========================================"
echo "AUTO FUTURES V8 — FAIL-CLOSED LIVE READY"
echo "24/7 | EXISTING HUB PER-TRADE CONFIRMATION"
echo "MAX 5 ISOLATED | 3-AI HOLD/REDUCE/EXIT GUARDIAN"
echo "========================================"

echo; echo "=== 1/12 CONTINUOUS ENTRY LEARNING ==="
python3 auto-futures-v1/learning/continuous_learner.py

echo; echo "=== 2/12 LIQUID FUTURES + DEEP MTF SCANNER ==="
python3 auto-futures-v1/paper_trader.py

echo; echo "=== 3/12 VERIFIED MARKET CONTEXT CACHE ==="
python3 auto-futures-v1/research/market_context_monitor.py

echo; echo "=== 4/12 EVENT-GATED THREE AI REVIEWERS ==="
python3 auto-futures-v1/ai/consensus.py

echo; echo "=== 5/12 ADAPTIVE PER-TRADE RISK ==="
python3 auto-futures-v1/risk/risk_engine.py

echo; echo "=== 6/12 EXECUTION GUARD ==="
python3 auto-futures-v1/execution/execution_guard.py

echo; echo "=== 7/12 3-AI + CONTEXT POSITION GUARDIAN ==="
python3 auto-futures-v1/position/ai_position_guardian.py

echo; echo "=== 8/12 PAPER EXECUTOR ==="
python3 auto-futures-v1/execution/paper_executor.py

echo; echo "=== 9/12 POSITION MANAGER ==="
python3 auto-futures-v1/position/position_manager.py

echo; echo "=== 10/12 RESEARCH JOURNAL ==="
python3 auto-futures-v1/research/learning_engine.py

echo; echo "=== 11/12 BINANCE LIVE PREFLIGHT — NO ORDER AUTHORITY ==="
python3 auto-futures-v1/execution/live_preflight.py

echo; echo "=== 12/12 HUB APPROVAL QUEUE ==="
python3 auto-futures-v1/execution/approval_queue.py

echo
echo "========================================"
echo "PIPELINE COMPLETE"
echo "V8 FAIL-CLOSED LIVE PREFLIGHT ACTIVE"
echo "3AI TOKENS: EVENT-GATED + 90S CACHE + COMPACT PAYLOAD"
echo "PREFLIGHT BLOCK => NO HUB TRADE APPROVAL"
echo "FULL 5/5 => NO NEW HUB TRADE NOTIFICATIONS"
echo "LIVE ORDER REQUIRES EXISTING HUB CONFIRMATION"
echo "NO REAL BINANCE ORDER WAS SENT"
echo "========================================"
