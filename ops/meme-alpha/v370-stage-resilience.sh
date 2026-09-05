#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v370-resilience-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
RT_NAME=realtime-pool-pulse-v370-resilient.js
WH_NAME=whale-flow-v370-adaptive-budget.js
RT_SRC="$ROOT/ops/meme-alpha/v370-realtime-pool-pulse-resilient.js"
WH_SRC="$ROOT/ops/meme-alpha/v370-whale-flow-adaptive-budget.js"
mkdir -p "$STAGE" "$DEPLOY"
/usr/bin/node --check "$RT_SRC"
/usr/bin/node --check "$WH_SRC"
RT_TEST=$(/usr/bin/node "$RT_SRC" --self-test)
WH_TEST=$(/usr/bin/node "$WH_SRC" --self-test)
echo "$RT_TEST"
echo "$WH_TEST"
echo "$RT_TEST" | grep -q 'V370_REALTIME_RESILIENT_SELF_TEST=PASS'
echo "$RT_TEST" | grep -q 'SINGLE_CONNECT_IN_FLIGHT=TRUE'
echo "$RT_TEST" | grep -q 'EXPONENTIAL_RECONNECT_BACKOFF=TRUE'
echo "$RT_TEST" | grep -q 'SET_ROTATION_THROTTLED_30S=TRUE'
echo "$WH_TEST" | grep -q 'V370_WHALE_ADAPTIVE_BUDGET_SELF_TEST=PASS'
echo "$WH_TEST" | grep -q 'RPC_CYCLE_15S=TRUE'
echo "$WH_TEST" | grep -q 'RPC_SPACING_1800MS=TRUE'
echo "$WH_TEST" | grep -q 'RATE_LIMIT_COOLDOWN_UP_TO_300S=TRUE'
install -m 0644 "$RT_SRC" "$DEPLOY/$RT_NAME"
install -m 0644 "$WH_SRC" "$DEPLOY/$WH_NAME"
RT_SHA=$(sha256sum "$DEPLOY/$RT_NAME" | awk '{print $1}')
WH_SHA=$(sha256sum "$DEPLOY/$WH_NAME" | awk '{print $1}')
printf '%s\n' "$RT_NAME" > "$STAGE/realtime-name.txt"
printf '%s\n' "$RT_SHA" > "$STAGE/realtime.sha256"
printf '%s\n' "$WH_NAME" > "$STAGE/whale-name.txt"
printf '%s\n' "$WH_SHA" > "$STAGE/whale.sha256"
echo V370_REALTIME_SHA256="$RT_SHA"
echo V370_WHALE_SHA256="$WH_SHA"
echo V370_RESILIENCE_STAGE_READY=TRUE
