#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v375-opportunity-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=safe-signal-export-v375-opportunity-accelerator.js
SRC="$ROOT/ops/meme-alpha/v375-safe-signal-opportunity-accelerator.js"
mkdir -p "$STAGE" "$DEPLOY"
/usr/bin/node --check "$SRC"
TEST=$(/usr/bin/node "$SRC" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'V375_OPPORTUNITY_ACCELERATOR_SELF_TEST=PASS'
echo "$TEST" | grep -q 'REALTIME_BURST_PROMOTION=TRUE'
echo "$TEST" | grep -q 'HARD_GUARDS_PRESERVED=TRUE'
echo "$TEST" | grep -q 'SELL_ROUTE_REQUIRED=TRUE'
echo "$TEST" | grep -q 'BOTH_FEEDS_DOWN_FAIL_CLOSED=TRUE'
grep -q '3.60.0-profit-aware-exits' "$APP/src/micro-live-executor.js"
grep -q 'FAST_DISCOVERY_V372' "$APP/src/new-listing-radar.js"
grep -q 'FAST_DISCOVERY_V372_MERGE' "$APP/src/scanner.js"
install -m 0644 "$SRC" "$DEPLOY/$NAME"
SHA=$(sha256sum "$DEPLOY/$NAME" | awk '{print $1}')
printf '%s\n' "$NAME" > "$STAGE/deploy-name.txt"
printf '%s\n' "$SHA" > "$STAGE/signal.sha256"
echo V375_SIGNAL_SHA256="$SHA"
echo V375_OPPORTUNITY_STAGE_READY=TRUE
