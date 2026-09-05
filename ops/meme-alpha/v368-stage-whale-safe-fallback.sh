#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v368-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=whale-flow-v368-safe-fallback.js
mkdir -p "$STAGE" "$DEPLOY"
cp "$ROOT/ops/meme-alpha/v365-whale-flow-rate-shaped.js" "$STAGE/$NAME"
/usr/bin/node --check "$STAGE/$NAME"
TEST=$(/usr/bin/node "$STAGE/$NAME" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'V365_WHALE_RATE_SHAPED_SELF_TEST=PASS'
echo "$TEST" | grep -q 'SERIAL_ONE_MINT_PER_CYCLE=TRUE'
echo "$TEST" | grep -q 'RPC_429_EXPONENTIAL_COOLDOWN=TRUE'
echo "$TEST" | grep -q 'HELD_POSITIONS_ALWAYS_MONITORED=TRUE'
install -m 0644 "$STAGE/$NAME" "$DEPLOY/$NAME"
sha256sum "$DEPLOY/$NAME" | awk '{print $1}' > "$STAGE/whale.sha256"
echo V368_WHALE_SHA=$(cat "$STAGE/whale.sha256")
echo V368_WHALE_SAFE_FALLBACK_STAGE_READY=TRUE
