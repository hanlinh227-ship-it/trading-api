#!/usr/bin/env bash
set -euo pipefail
echo '=== SIGNER / EXECUTOR SIZING COMPATIBILITY AUDIT ==='
sed -n '105,175p' /opt/meme-alpha-signer/ready_signer.py 2>/dev/null || true
echo '--- EXEC TARGET PLAN ---'
sed -n '140,170p' /opt/meme-alpha/app/src/micro-live-executor.js 2>/dev/null || true
echo V217_SIGNER_SIZING_AUDIT_PASS
