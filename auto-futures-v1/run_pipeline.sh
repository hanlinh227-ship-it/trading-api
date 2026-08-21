#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/trading/trading-api"
cd "$ROOT"
if [[ -f /opt/trading/.env.ai ]]; then set -a; source /opt/trading/.env.ai; set +a; fi
if [[ -f /opt/trading/.env.binance ]]; then set -a; source /opt/trading/.env.binance; set +a; fi
if [[ -f /opt/trading/.env.telegram ]]; then set -a; source /opt/trading/.env.telegram; set +a; fi

echo
echo "========================================"
echo "AUTO FUTURES V10 — COORDINATED SIGNAL INTELLIGENCE"
echo "24/7 | EXISTING HUB PER-TRADE CONFIRMATION"
echo "MAX 5 ISOLATED | 3-AI COUNCIL | FAIL-CLOSED"
echo "========================================"

echo; echo "=== 1/14 CONTINUOUS ENTRY LEARNING ==="
python3 auto-futures-v1/learning/continuous_learner.py

echo; echo "=== 2/14 LIQUID FUTURES + DEEP MTF SCANNER ==="
python3 auto-futures-v1/paper_trader.py

echo; echo "=== 3/14 VERIFIED MARKET CONTEXT CACHE ==="
python3 auto-futures-v1/research/market_context_monitor.py

echo; echo "=== 4/14 DETERMINISTIC SIGNAL QUALITY GUARD ==="
python3 auto-futures-v1/research/signal_quality_guard.py

echo; echo "=== 5/14 EVENT-GATED THREE AI COUNCIL ==="
python3 auto-futures-v1/ai/consensus.py

echo; echo "=== 6/14 ADAPTIVE PER-TRADE RISK ==="
python3 auto-futures-v1/risk/risk_engine.py

echo; echo "=== 7/14 EXECUTION GUARD ==="
python3 auto-futures-v1/execution/execution_guard.py

echo; echo "=== 8/14 3-AI + CONTEXT POSITION GUARDIAN ==="
python3 auto-futures-v1/position/ai_position_guardian.py

echo; echo "=== 9/14 PAPER EXECUTOR ==="
python3 auto-futures-v1/execution/paper_executor.py

echo; echo "=== 10/14 POSITION MANAGER ==="
python3 auto-futures-v1/position/position_manager.py

echo; echo "=== 11/14 RESEARCH JOURNAL ==="
python3 auto-futures-v1/research/learning_engine.py

echo; echo "=== 12/14 BINANCE LIVE PREFLIGHT — ACCOUNT-SOURCED SIZING ==="
python3 auto-futures-v1/execution/live_preflight.py

echo; echo "=== 13/14 EVENT-GATED 3-AI RELIABILITY COUNCIL ==="
python3 auto-futures-v1/research/reliability_learner.py

echo; echo "=== 14/14 HUB APPROVAL QUEUE ==="
python3 auto-futures-v1/execution/approval_queue.py

echo
echo "========================================"
echo "PIPELINE COMPLETE"
echo "V10 SIGNAL QUALITY + COORDINATED 3-AI ACTIVE"
echo "SCANNER FEATURES NORMALIZED BEFORE AI REVIEW"
echo "PREFLIGHT/INCIDENT/HIGH RELIABILITY BLOCK => NO HUB APPROVAL"
echo "LIVE ORDER REQUIRES EXISTING HUB CONFIRMATION"
echo "========================================"
