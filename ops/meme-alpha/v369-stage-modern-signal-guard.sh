#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v369-signal-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=safe-signal-export-v369-modern-guard.js
SRC="$ROOT/ops/meme-alpha/v369-safe-signal-modern-guard.js"
mkdir -p "$STAGE" "$DEPLOY"
/usr/bin/node --check "$SRC"
TEST=$(/usr/bin/node "$SRC" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'V369_SIGNAL_GUARD_SELF_TEST=PASS'
echo "$TEST" | grep -q 'ENTRY_FAIL_CLOSED_WHEN_BOTH_INTEL_DOWN=TRUE'
echo "$TEST" | grep -q 'DEGRADED_INTEL_SCORE_HAIRCUT=TRUE'
echo "$TEST" | grep -q 'FRESH_WHALE_RUG_GUARD=TRUE'
echo "$TEST" | grep -q 'TOKEN_EXTENSION_ENTRY_GUARD=TRUE'
install -m 0644 "$SRC" "$DEPLOY/$NAME"
SHA=$(sha256sum "$DEPLOY/$NAME" | awk '{print $1}')
printf '%s\n' "$NAME" > "$STAGE/deploy-name.txt"
printf '%s\n' "$SHA" > "$STAGE/signal.sha256"
echo V369_SIGNAL_SHA256="$SHA"
echo V369_SIGNAL_STAGE_READY=TRUE
