#!/usr/bin/env bash
set -euo pipefail
echo '=== SAFE DEPLOY DISPATCHER ==='
sed -n '1,220p' /usr/local/sbin/meme-alpha-safe-deploy
echo V360_SAFE_DEPLOY_INSPECT=COMPLETE
