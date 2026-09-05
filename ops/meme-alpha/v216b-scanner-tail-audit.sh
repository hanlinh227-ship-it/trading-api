#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== MEME ALPHA v2.16B SCANNER TAIL AUDIT ==='
sed -n '880,1100p' src/scanner.js
echo V216B_SCANNER_TAIL_AUDIT_PASS
