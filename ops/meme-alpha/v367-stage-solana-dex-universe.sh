#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v367-stage"
BASE="$APP/runtime-status/deploy-candidates"
mkdir -p "$STAGE" "$BASE"

/usr/bin/node --check ops/meme-alpha/v367-solana-dex-universe-radar.js
/usr/bin/node ops/meme-alpha/v367-solana-dex-universe-radar.js --self-test | tee "$STAGE/radar-selftest.txt"
grep -q 'V367_SOLANA_DEX_UNIVERSE_SELF_TEST=PASS' "$STAGE/radar-selftest.txt"
grep -q 'DISCOVERY_ONLY_ENTRY_GATES_UNCHANGED=TRUE' "$STAGE/radar-selftest.txt"

RADAR_NAME=radar-v367-solana-dex-universe.js
SCANNER_NAME=scanner-v367-broad-dex-universe.js
install -m 0644 ops/meme-alpha/v367-solana-dex-universe-radar.js "$BASE/$RADAR_NAME"
cp /opt/meme-alpha/app/src/scanner.js "$STAGE/scanner-base.js"
python3 ops/meme-alpha/v367-patch-scanner-broad-dex-universe.py "$STAGE/scanner-base.js" | tee "$STAGE/scanner-patch.txt"
grep -q 'V367_SCANNER_BROAD_DEX_PATCH=PASS' "$STAGE/scanner-patch.txt"
/usr/bin/node --check "$STAGE/scanner-base.js"
install -m 0644 "$STAGE/scanner-base.js" "$BASE/$SCANNER_NAME"
sha256sum "$BASE/$RADAR_NAME" | awk '{print $1}' > "$STAGE/radar.sha256"
sha256sum "$BASE/$SCANNER_NAME" | awk '{print $1}' > "$STAGE/scanner.sha256"
echo V367_RADAR_SHA=$(cat "$STAGE/radar.sha256")
echo V367_SCANNER_SHA=$(cat "$STAGE/scanner.sha256")
echo V367_SOLANA_DEX_UNIVERSE_STAGE_READY=TRUE
