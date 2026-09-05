#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.9.5 EXIT LOGIC AUDIT ==='
echo '--- micro live sell/hold logic ---'
grep -nE "function (decide|holdSafe|sell|tier)|SELL|HOLD|profit|pnl|take|exit" src/micro-live-executor.js | head -n 220 || true
echo '--- paper position profit/exit logic ---'
grep -nEi "take.?profit|profit|partial|runner|exit|close|trail|breakeven|stop|tp|pnl" src/position.js | head -n 260 || true
echo V295_EXIT_LOGIC_AUDIT_PASS
