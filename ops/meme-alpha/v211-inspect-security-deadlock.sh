#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== HOLDER CLUSTER CONTEXT 430-590 ==='
sed -n '430,590p' src/holder-cluster.js || true
echo '=== HOLDER CLUSTER CONTEXT 590-670 ==='
sed -n '590,670p' src/holder-cluster.js || true
echo '=== SECURITY CONTEXT 300-370 ==='
sed -n '300,370p' src/security.js || true
echo '=== CURRENT UNIVERSE/SCANNER HOOKS ==='
grep -n -E 'holder-cluster|security.js|cycle5' package.json run-paper.sh 2>/dev/null || true
echo V211_INSPECT_CONTEXT_PASS
