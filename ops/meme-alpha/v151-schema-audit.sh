#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== SCANNER FIELD HINTS ==='
grep -nE 'candidate|tags|source|symbol|name|mint|organic|firstPool|tokenProgram|token2022|category' src/scanner.js | head -n 260 || true
echo '=== POSITION ID/TRADE HINTS ==='
grep -nE 'positionId|openPositions|PAPER_BUY|PAPER_SELL|id:' src/position.js | head -n 260 || true
echo '=== PERSISTENCE HINTS ==='
grep -nE 'universeClass|decision|securityDecision|hardReject|token2022|persistenceDecision|observations|tags' src/persistence.js | head -n 260 || true
echo 'V151_SCHEMA_AUDIT_COMPLETE'
