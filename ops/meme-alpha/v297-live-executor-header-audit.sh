#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== LIVE EXECUTOR HEADER 1-90 ==='
nl -ba src/micro-live-executor.js | sed -n '1,90p'
echo '=== ROOT POLICY 1-120 ==='
[ -f /etc/meme-alpha/micro-live-policy.json ] && cat /etc/meme-alpha/micro-live-policy.json || true
echo V297_LIVE_EXECUTOR_HEADER_AUDIT_PASS
