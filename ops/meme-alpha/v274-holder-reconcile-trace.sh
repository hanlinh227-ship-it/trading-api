#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== HOLDER 530-640 ==='
sed -n '530,640p' src/holder-cluster.js
echo '=== SECURITY 300-380 ==='
sed -n '300,380p' src/security.js
echo '=== PACKAGE CYCLE ==='
cat package.json | sed -n '1,220p'
echo V274_HOLDER_RECONCILE_TRACE_PASS
