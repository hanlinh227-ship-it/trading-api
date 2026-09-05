#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v369-whale-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=whale-flow-v369-modern.js
SRC="$ROOT/ops/meme-alpha/v369-whale-flow-modern.js"
mkdir -p "$STAGE" "$DEPLOY"
/usr/bin/node --check "$SRC"
TEST=$(/usr/bin/node "$SRC" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'V369_WHALE_MODERN_SELF_TEST=PASS'
echo "$TEST" | grep -q 'MULTI_PROVIDER_FAILOVER=TRUE'
echo "$TEST" | grep -q 'PER_PROVIDER_429_COOLDOWN=TRUE'
echo "$TEST" | grep -q 'ONE_MINT_PER_CYCLE=TRUE'
echo "$TEST" | grep -q 'SUPPLY_CACHE_10M=TRUE'
echo "$TEST" | grep -q 'HELD_POSITIONS_PRIORITY=TRUE'
install -m 0644 "$SRC" "$DEPLOY/$NAME"
SHA=$(sha256sum "$DEPLOY/$NAME" | awk '{print $1}')
printf '%s\n' "$NAME" > "$STAGE/deploy-name.txt"
printf '%s\n' "$SHA" > "$STAGE/whale.sha256"
echo V369_WHALE_SHA256="$SHA"
echo V369_WHALE_STAGE_READY=TRUE
