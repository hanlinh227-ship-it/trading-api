#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
echo '=== HOLDER CLUSTER CODE AUDIT 260-749 ==='
sed -n '260,749p' src/holder-cluster.js || true
echo V214_HOLDER_CLUSTER_CODE_AUDIT_2_PASS
