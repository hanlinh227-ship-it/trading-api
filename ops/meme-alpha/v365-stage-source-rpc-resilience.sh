#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v365-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
mkdir -p "$STAGE" "$DEPLOY"
SC_NAME=scanner-v365-source-resilient.js
WH_NAME=whale-flow-v365-rate-shaped.js
cp "$APP/src/scanner.js" "$STAGE/$SC_NAME"
python3 "$ROOT/ops/meme-alpha/v365-patch-scanner-source-resilience.py" "$STAGE/$SC_NAME"
cp "$ROOT/ops/meme-alpha/v365-whale-flow-rate-shaped.js" "$STAGE/$WH_NAME"
/usr/bin/node --check "$STAGE/$SC_NAME"
/usr/bin/node --check "$STAGE/$WH_NAME"
WT=$(/usr/bin/node "$STAGE/$WH_NAME" --self-test); echo "$WT"
echo "$WT" | grep -q 'V365_WHALE_RATE_SHAPED_SELF_TEST=PASS'
echo "$WT" | grep -q 'SERIAL_ONE_MINT_PER_CYCLE=TRUE'
echo "$WT" | grep -q 'RPC_429_EXPONENTIAL_COOLDOWN=TRUE'
grep -q 'JUPITER_MIN_INTERVAL_MS = 3200' "$STAGE/$SC_NAME"
grep -q 'DISCOVERY_RADAR_MIN_MATCHES = 3' "$STAGE/$SC_NAME"
grep -q 'providerRedundancy' "$STAGE/$SC_NAME"
grep -q 'i >= 1 && successfulSources >= 1' "$STAGE/$SC_NAME"
install -m 0644 "$STAGE/$SC_NAME" "$DEPLOY/$SC_NAME"
install -m 0644 "$STAGE/$WH_NAME" "$DEPLOY/$WH_NAME"
sha256sum "$DEPLOY/$SC_NAME" | awk '{print $1}' > "$STAGE/scanner.sha256"
sha256sum "$DEPLOY/$WH_NAME" | awk '{print $1}' > "$STAGE/whale.sha256"
echo V365_SCANNER_SHA=$(cat "$STAGE/scanner.sha256")
echo V365_WHALE_SHA=$(cat "$STAGE/whale.sha256")
echo V365_SOURCE_RPC_STAGE_READY=TRUE
