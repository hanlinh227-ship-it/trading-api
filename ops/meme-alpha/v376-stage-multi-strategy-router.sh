#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v376-router-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=safe-signal-export-v376-multi-strategy-router.js
SRC="$ROOT/ops/meme-alpha/v376-safe-signal-multi-strategy-router.js"
mkdir -p "$STAGE" "$DEPLOY"

/usr/bin/node --check "$SRC"
TEST=$(/usr/bin/node "$SRC" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'V376_MULTI_STRATEGY_ROUTER_SELF_TEST=PASS'
echo "$TEST" | grep -q 'EXECUTOR_CORE_SAFETY_CONTRACT_PRESERVED=TRUE'
echo "$TEST" | grep -q 'SECURITY_PASS_REQUIRED=TRUE'
echo "$TEST" | grep -q 'HOLDER_PASS_REQUIRED=TRUE'
echo "$TEST" | grep -q 'SELL_ROUTE_REQUIRED=TRUE'
echo "$TEST" | grep -q 'TOKEN2022_HARD_BLOCK_PRESERVED=TRUE'
echo "$TEST" | grep -q 'BOTH_FEEDS_DOWN_FAIL_CLOSED=TRUE'

# Compatibility locks: expand opportunity lanes only; preserve discovery, realtime and executor.
grep -q 'FAST_DISCOVERY_V372' "$APP/src/new-listing-radar.js"
grep -q 'FAST_DISCOVERY_V372_MERGE' "$APP/src/scanner.js"
grep -q 'DISCOVERY_RADAR_ONLY_MAX = 240' "$APP/src/scanner.js"
grep -q '3.60.0-profit-aware-exits' "$APP/src/micro-live-executor.js"

test -s "$APP/runtime-status/realtime-pool-pulse.json"
/usr/bin/node - "$APP/runtime-status/realtime-pool-pulse.json" <<'NODE'
const fs=require('fs');const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
if(x.version!=='3.74.0-held-continuity'||x.status!=='HEALTHY')throw new Error('V374_REALTIME_REQUIRED');
console.log('V374_REALTIME_COMPATIBILITY=PASS');
NODE

cp "$APP/runtime-status/signal-snapshot.json" "$STAGE/signal-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/signal-before.json"
cp "$APP/runtime-status/portfolio-observability.json" "$STAGE/portfolio-before.json" 2>/dev/null || printf '%s\n' '{}' > "$STAGE/portfolio-before.json"
install -m 0644 "$SRC" "$DEPLOY/$NAME"
SHA=$(sha256sum "$DEPLOY/$NAME" | awk '{print $1}')
printf '%s\n' "$NAME" > "$STAGE/deploy-name.txt"
printf '%s\n' "$SHA" > "$STAGE/signal.sha256"
echo V376_SIGNAL_SHA256="$SHA"
echo V376_LANES=LAUNCH_FAST,MOMENTUM,RECOVERY_FLOW,ESTABLISHED_ROTATION
echo V376_ROUTER_STAGE_READY=TRUE
