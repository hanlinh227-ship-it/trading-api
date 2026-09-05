#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== PERSISTENCE READY LOGIC ==='
grep -n -E 'consecutive|ready|READY|avg|liquidity|persistenceDecision|eligible' src/persistence.js | tail -n 240 || true
echo '=== RISK ENTRY LOGIC ==='
grep -n -E 'candidate|ready|READY|persistence|entryAllowed|PROBE_CANDIDATE|securityDecision|sellRoute' src/risk.js | tail -n 240 || true
echo '=== POSITION ENTRY LOGIC ==='
grep -n -E 'candidate|ready|READY|persistence|entryAllowed|PROBE_CANDIDATE|securityDecision|sellRoute' src/position.js | tail -n 260 || true
echo V215_INSPECT_PASS
