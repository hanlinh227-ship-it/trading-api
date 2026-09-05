#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== HOLDER CLUSTER KEY LINES ==='
grep -n -E 'DEV_IDENTITY|REVIEW|BLOCK|cluster|owner' src/holder-cluster.js | tail -n 120 || true
echo '=== SECURITY KEY LINES ==='
grep -n -E 'holder|cluster|REVIEW|BLOCK|securityDecision|reasons' src/security.js | tail -n 160 || true
echo '=== CURRENT UNIVERSE/SCANNER HOOKS ==='
grep -n -E 'holder-cluster|security.js|cycle5' package.json run-paper.sh 2>/dev/null || true
echo V211_INSPECT_PASS
