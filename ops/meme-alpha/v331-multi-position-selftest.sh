#!/usr/bin/env bash
set -euo pipefail
CAND="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/micro-live/micro-live-executor-v331-multi.js"
PROD=/opt/meme-alpha/app/src/micro-live-executor.js

echo '=== V331 MULTI POSITION SELF TEST ==='
/usr/bin/node --check "$CAND"
/usr/bin/node "$CAND" --self-test
sha256sum "$CAND" | sed 's/^/CANDIDATE_SHA256=/'
stat -c 'PROD owner=%U group=%G mode=%a writable_by_runner=%A path=%n' "$PROD"
if [ -w "$PROD" ]; then echo PROD_DIRECT_WRITABLE=true; else echo PROD_DIRECT_WRITABLE=false; fi
if [ -w "$(dirname "$PROD")" ]; then echo PROD_PARENT_WRITABLE=true; else echo PROD_PARENT_WRITABLE=false; fi

echo '=== MICRO LIVE UNIT ==='
systemctl show meme-alpha-micro-live.service -p User -p Group -p SupplementaryGroups -p ExecStart -p FragmentPath -p ActiveState -p SubState -p NRestarts --no-pager 2>/dev/null || true

echo '=== NARROW SUDO CAPABILITIES ==='
sudo -n -l 2>&1 | sed -E 's/(PASSWD|password).*/<redacted>/Ig' || true

echo '=== CURRENT PRODUCTION HASH ==='
sha256sum "$PROD"
echo V331_MULTI_POSITION_SELFTEST_PASS
