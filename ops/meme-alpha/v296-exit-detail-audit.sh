#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== LIVE EXIT DETAIL 80-175 ==='
nl -ba src/micro-live-executor.js | sed -n '80,175p'
echo '=== PAPER EXIT DETAIL 520-735 ==='
nl -ba src/position.js | sed -n '520,735p'
echo V296_EXIT_DETAIL_AUDIT_PASS
