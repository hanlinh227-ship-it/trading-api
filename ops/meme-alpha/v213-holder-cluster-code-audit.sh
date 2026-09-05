#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== HOLDER CLUSTER CODE AUDIT ==='
wc -l src/holder-cluster.js || true
sed -n '1,260p' src/holder-cluster.js || true
echo V213_HOLDER_CLUSTER_CODE_AUDIT_PASS
