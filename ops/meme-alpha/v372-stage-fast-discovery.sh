#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v372-fast-discovery-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
RADAR_NAME=radar-v372-fast-discovery.js
SCANNER_NAME=scanner-v372-fast-discovery.js
REALTIME_NAME=realtime-v372-fast-hotset.js
mkdir -p "$STAGE" "$DEPLOY"

test -s "$APP/src/new-listing-radar.js"
test -s "$APP/src/scanner.js"
cp "$APP/src/new-listing-radar.js" "$STAGE/radar.js"
cp "$APP/src/scanner.js" "$STAGE/scanner.js"

python3 "$ROOT/ops/meme-alpha/v372-patch-radar-fast-discovery.py" "$STAGE/radar.js" | tee "$STAGE/radar-patch.txt"
python3 "$ROOT/ops/meme-alpha/v372-patch-scanner-fast-discovery.py" "$STAGE/scanner.js" | tee "$STAGE/scanner-patch.txt"

grep -Eq 'V372_RADAR_FAST_DISCOVERY_PATCH=PASS|V372_RADAR_ALREADY_PATCHED=TRUE' "$STAGE/radar-patch.txt"
grep -Eq 'V372_SCANNER_FAST_DISCOVERY_PATCH=PASS|V372_SCANNER_ALREADY_PATCHED=TRUE' "$STAGE/scanner-patch.txt"
/usr/bin/node --check "$STAGE/radar.js"
/usr/bin/node --check "$STAGE/scanner.js"
/usr/bin/node --check "$ROOT/ops/meme-alpha/v372-realtime-hotset.js"

RADAR_TEST=$(/usr/bin/node "$STAGE/radar.js" --self-test)
REALTIME_TEST=$(/usr/bin/node "$ROOT/ops/meme-alpha/v372-realtime-hotset.js" --self-test)
echo "$RADAR_TEST"
echo "$REALTIME_TEST"
echo "$RADAR_TEST" | grep -q 'V372_FAST_DISCOVERY_SELF_TEST=PASS'
echo "$RADAR_TEST" | grep -q 'FAST_DISCOVERY_NEVER_GRANTS_ENTRY=TRUE'
echo "$REALTIME_TEST" | grep -q 'V372_REALTIME_HOTSET_SELF_TEST=PASS'
echo "$REALTIME_TEST" | grep -q 'HELD_POSITIONS_PRIORITY=TRUE'
echo "$REALTIME_TEST" | grep -q 'FAST_DISCOVERY_PRIORITY=TRUE'

grep -q 'FAST_DISCOVERY_V372_MERGE' "$STAGE/scanner.js"
grep -q 'DISCOVERY_RADAR_ONLY_MAX = 240' "$STAGE/scanner.js"
grep -q 'FAST_DISCOVERY_NEVER_GRANTS_ENTRY' "$ROOT/ops/meme-alpha/v372-patch-scanner-fast-discovery.py"
grep -q '3.60.0-profit-aware-exits' "$APP/src/micro-live-executor.js"

install -m 0644 "$STAGE/radar.js" "$DEPLOY/$RADAR_NAME"
install -m 0644 "$STAGE/scanner.js" "$DEPLOY/$SCANNER_NAME"
install -m 0644 "$ROOT/ops/meme-alpha/v372-realtime-hotset.js" "$DEPLOY/$REALTIME_NAME"

RADAR_SHA=$(sha256sum "$DEPLOY/$RADAR_NAME" | awk '{print $1}')
SCANNER_SHA=$(sha256sum "$DEPLOY/$SCANNER_NAME" | awk '{print $1}')
REALTIME_SHA=$(sha256sum "$DEPLOY/$REALTIME_NAME" | awk '{print $1}')
printf '%s\n' "$RADAR_NAME" > "$STAGE/radar-name.txt"
printf '%s\n' "$SCANNER_NAME" > "$STAGE/scanner-name.txt"
printf '%s\n' "$REALTIME_NAME" > "$STAGE/realtime-name.txt"
printf '%s\n' "$RADAR_SHA" > "$STAGE/radar.sha256"
printf '%s\n' "$SCANNER_SHA" > "$STAGE/scanner.sha256"
printf '%s\n' "$REALTIME_SHA" > "$STAGE/realtime.sha256"
echo V372_RADAR_SHA256="$RADAR_SHA"
echo V372_SCANNER_SHA256="$SCANNER_SHA"
echo V372_REALTIME_SHA256="$REALTIME_SHA"
echo V372_FAST_DISCOVERY_STAGE_READY=TRUE
