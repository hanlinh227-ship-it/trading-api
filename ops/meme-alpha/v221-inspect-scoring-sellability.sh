#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== SCANNER SCORE REFERENCES ==='
grep -n -E 'score|netBuyers5m|buySell|txRatio|organic|momentum|PROBE_CANDIDATE|sellability|swap/v2/order' src/scanner.js | head -n 260 || true
echo '=== SCANNER SCORE FUNCTION CONTEXT ==='
LINE=$(grep -n -m1 'function score\|const scoreToken\|function evaluate' src/scanner.js | cut -d: -f1 || true)
if [ -n "$LINE" ]; then START=$((LINE-20)); [ "$START" -lt 1 ] && START=1; END=$((LINE+220)); sed -n "${START},${END}p" src/scanner.js; fi
echo '=== SELLABILITY CONTEXT ==='
LINE=$(grep -n -m1 'async function sellability\|const sellability' src/scanner.js | cut -d: -f1 || true)
if [ -n "$LINE" ]; then START=$((LINE-30)); [ "$START" -lt 1 ] && START=1; END=$((LINE+120)); sed -n "${START},${END}p" src/scanner.js; fi
echo V221_INSPECT_PASS
