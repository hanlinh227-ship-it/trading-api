#!/usr/bin/env bash
set -euo pipefail
P=/opt/meme-alpha/app/src/micro-live-executor.js
[ -r "$P" ] || { echo V330_FAIL=EXECUTOR_UNREADABLE; exit 1; }
echo '=== V330 LIVE EXECUTOR SOURCE CAPTURE ==='
stat -c 'EXECUTOR owner=%U group=%G mode=%a size=%s' "$P"
sha256sum "$P" | sed 's/^/EXECUTOR_SHA256=/'
echo '=== EXECUTOR_SOURCE_BEGIN ==='
cat "$P"
echo '=== EXECUTOR_SOURCE_END ==='
echo V330_CAPTURE_PASS
