#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.16 SCANNER CODE AUDIT ==='
wc -l src/scanner.js || true
sed -n '1,260p' src/scanner.js
printf '\n--- SCANNER 261-520 ---\n'
sed -n '261,520p' src/scanner.js
printf '\n--- SCANNER 521-900 ---\n'
sed -n '521,900p' src/scanner.js
printf '\n--- SCANNER RUNTIME ---\n'
ps -eo pid,etimes,cmd | grep 'node src/scanner.js' | grep -v grep || true
printf '\n--- PAPER CYCLE COMMAND ---\n'
ps -eo pid,etimes,cmd | grep 'node src/scanner.js &&' | grep -v grep || true
echo V216_SCANNER_CODE_AUDIT_PASS
