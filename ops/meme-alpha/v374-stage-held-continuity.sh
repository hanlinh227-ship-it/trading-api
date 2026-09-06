#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v374-held-continuity-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
REALTIME_NAME=realtime-v374-held-continuity.js
mkdir -p "$STAGE" "$DEPLOY"

test -s "$ROOT/ops/meme-alpha/v374-realtime-held-continuity.js"
test -s "$APP/src/new-listing-radar.js"
test -s "$APP/src/scanner.js"
test -s "$APP/src/micro-live-executor.js"

/usr/bin/node --check "$ROOT/ops/meme-alpha/v374-realtime-held-continuity.js"
SELF_TEST=$(/usr/bin/node "$ROOT/ops/meme-alpha/v374-realtime-held-continuity.js" --self-test)
echo "$SELF_TEST"
echo "$SELF_TEST" | grep -q 'V374_HELD_CONTINUITY_SELF_TEST=PASS'
echo "$SELF_TEST" | grep -q 'TRUSTED_MINT_PAIR_CACHE=TRUE'
echo "$SELF_TEST" | grep -q 'NO_PAIR_GUESSING=TRUE'
echo "$SELF_TEST" | grep -q 'HELD_RESOLVED_UNRESOLVED_OBSERVABILITY=TRUE'
echo "$SELF_TEST" | grep -q 'INCREMENTAL_SUBSCRIPTIONS=TRUE'
echo "$SELF_TEST" | grep -q 'HOTSET_CHANGE_RECONNECT=FALSE'
echo "$SELF_TEST" | grep -q 'FAST_DISCOVERY_PRIORITY=TRUE'
echo "$SELF_TEST" | grep -q 'EXIT_PATH_UNTOUCHED=TRUE'

# Compatibility guards: v3.74 changes realtime continuity only.
# Discovery, signal safety and profit-aware exits must remain unchanged.
grep -q 'FAST_DISCOVERY_V372' "$APP/src/new-listing-radar.js"
grep -q 'FAST_DISCOVERY_V372_MERGE' "$APP/src/scanner.js"
grep -q 'DISCOVERY_RADAR_ONLY_MAX = 240' "$APP/src/scanner.js"
grep -q '3.60.0-profit-aware-exits' "$APP/src/micro-live-executor.js"

cp "$APP/runtime-status/portfolio-observability.json" "$STAGE/portfolio-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/portfolio-before.json"
cp "$APP/runtime-status/signal-snapshot.json" "$STAGE/signal-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/signal-before.json"
cp "$APP/runtime-status/realtime-pool-pulse.json" "$STAGE/realtime-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/realtime-before.json"

install -m 0644 "$ROOT/ops/meme-alpha/v374-realtime-held-continuity.js" "$DEPLOY/$REALTIME_NAME"
REALTIME_SHA=$(sha256sum "$DEPLOY/$REALTIME_NAME" | awk '{print $1}')
printf '%s\n' "$REALTIME_NAME" > "$STAGE/realtime-name.txt"
printf '%s\n' "$REALTIME_SHA" > "$STAGE/realtime.sha256"
echo V374_REALTIME_SHA256="$REALTIME_SHA"
echo V374_CACHE_TTL_DAYS=7
echo V374_HOTSET_LIMIT=56
echo V374_HELD_CONTINUITY_STAGE_READY=TRUE
