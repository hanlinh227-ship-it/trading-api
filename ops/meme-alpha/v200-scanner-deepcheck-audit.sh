#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== SCANNER DEEP CHECK AUDIT ==='
grep -n -C 8 -E 'slice\(0, ?20\)|deepCheck|deep-check|sellRoute|DEX|dexscreener|order\?' src/scanner.js | head -n 500 || true
echo V200_SCANNER_AUDIT_PASS
