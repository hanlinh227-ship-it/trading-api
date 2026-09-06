#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v373-reactive-market-fabric-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
REALTIME_NAME=realtime-v373-reactive-market-fabric.js
mkdir -p "$STAGE" "$DEPLOY"

test -s "$ROOT/ops/meme-alpha/v373-realtime-reactive.js"
test -s "$APP/src/new-listing-radar.js"
test -s "$APP/src/scanner.js"
test -s "$APP/src/micro-live-executor.js"

/usr/bin/node --check "$ROOT/ops/meme-alpha/v373-realtime-reactive.js"
SELF_TEST=$(/usr/bin/node "$ROOT/ops/meme-alpha/v373-realtime-reactive.js" --self-test)
echo "$SELF_TEST"
echo "$SELF_TEST" | grep -q 'V373_REACTIVE_FABRIC_SELF_TEST=PASS'
echo "$SELF_TEST" | grep -q 'INCREMENTAL_SUBSCRIPTIONS=TRUE'
echo "$SELF_TEST" | grep -q 'HOTSET_CHANGE_RECONNECT=FALSE'
echo "$SELF_TEST" | grep -q 'SOLANA_SLOT_HEARTBEAT=TRUE'
echo "$SELF_TEST" | grep -q 'BOUNDED_RECONCILE_OPS=TRUE'
echo "$SELF_TEST" | grep -q 'ATOMIC_STATE_WRITES=TRUE'
echo "$SELF_TEST" | grep -q 'SINGLETON_GUARD=TRUE'

# Compatibility guards: v3.73 replaces only realtime discovery transport.
# It must not roll back discovery, signal safety, or profit-aware execution.
grep -q 'FAST_DISCOVERY_V372' "$APP/src/new-listing-radar.js"
grep -q 'FAST_DISCOVERY_V372_MERGE' "$APP/src/scanner.js"
grep -q 'DISCOVERY_RADAR_ONLY_MAX = 240' "$APP/src/scanner.js"
grep -q '3.60.0-profit-aware-exits' "$APP/src/micro-live-executor.js"

cp "$APP/runtime-status/portfolio-observability.json" "$STAGE/portfolio-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/portfolio-before.json"
cp "$APP/runtime-status/signal-snapshot.json" "$STAGE/signal-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/signal-before.json"

install -m 0644 "$ROOT/ops/meme-alpha/v373-realtime-reactive.js" "$DEPLOY/$REALTIME_NAME"
REALTIME_SHA=$(sha256sum "$DEPLOY/$REALTIME_NAME" | awk '{print $1}')
printf '%s\n' "$REALTIME_NAME" > "$STAGE/realtime-name.txt"
printf '%s\n' "$REALTIME_SHA" > "$STAGE/realtime.sha256"
echo V373_REALTIME_SHA256="$REALTIME_SHA"
echo V373_INCREMENTAL_RECONCILE_MS=100
echo V373_DESIRED_REFRESH_MS=250
echo V373_HOTSET_LIMIT=56
echo V373_REACTIVE_MARKET_FABRIC_STAGE_READY=TRUE
