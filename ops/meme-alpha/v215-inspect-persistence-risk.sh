#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== PERSISTENCE 280-455 ==='
sed -n '280,455p' src/persistence.js || true
echo '=== PERSISTENCE 580-620 ==='
sed -n '580,620p' src/persistence.js || true
echo '=== RISK 40-70 ==='
sed -n '40,70p' src/risk.js || true
echo '=== POSITION 835-915 ==='
sed -n '835,915p' src/position.js || true
echo V215_INSPECT_CONTEXT_PASS
