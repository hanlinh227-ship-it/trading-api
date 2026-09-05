#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== SCANNER 840-1010 ==='
sed -n '840,1010p' src/scanner.js
echo '=== SECURITY 80-300 ==='
sed -n '80,300p' src/security.js
echo '=== HOLDER 490-640 ==='
sed -n '490,640p' src/holder-cluster.js
echo '=== PERSISTENCE 285-475 ==='
sed -n '285,475p' src/persistence.js
echo '=== RUN PAPER ==='
sed -n '1,240p' run-paper.sh
echo V273_DEEPCHECK_TRACE_PASS
