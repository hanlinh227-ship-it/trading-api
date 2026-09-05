#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== SECURITY INSPECT FUNCTION ==='
sed -n '110,300p' src/security.js || true
echo '=== SCANNER SELLABILITY REFERENCES ==='
grep -n -E 'sellRoute|sellImpact|priceImpact|swap/v2/order|Jupiter|jupiter|deep|order\?' src/scanner.js | tail -n 220 || true
echo '=== SCANNER DEEP RANGE ==='
start=$(grep -n 'Deep-check\|baseDeep\|const deep' src/scanner.js | head -1 | cut -d: -f1 || true); if [ -n "$start" ]; then a=$((start-20)); [ $a -lt 1 ] && a=1; b=$((start+260)); sed -n "${a},${b}p" src/scanner.js; fi
echo V213_INSPECT_PASS
