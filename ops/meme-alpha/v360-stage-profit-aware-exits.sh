#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v360-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=micro-live-executor-v360-profit-aware.js
SRC="$APP/src/micro-live-executor.js"
OUT="$STAGE/$NAME"
mkdir -p "$STAGE" "$DEPLOY"
cp "$SRC" "$OUT"
python3 "$ROOT/ops/meme-alpha/v360-patch-profit-aware-exits.py" "$OUT"
/usr/bin/node --check "$OUT"
TEST=$(/usr/bin/node "$OUT" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS'
echo "$TEST" | grep -q 'PROFIT_AWARE_WEAK_EXIT=TRUE'
echo "$TEST" | grep -q 'POSITIVE_SOFT_WEAKNESS=PARTIAL_ONLY'
echo "$TEST" | grep -q 'WINNER_ROTATION_PROTECTION=TRUE'
echo "$TEST" | grep -q 'NO_QUOTE_WINNER_DEFENSE=TRUE'
echo "$TEST" | grep -q 'SEVERE_TREND_BREAK_FULL_EXIT=KEPT'
echo "$TEST" | grep -q 'HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT'
install -m 0644 "$OUT" "$DEPLOY/$NAME"
SHA=$(sha256sum "$DEPLOY/$NAME" | awk '{print $1}')
printf '%s\n' "$NAME" > "$STAGE/deploy-name.txt"
printf '%s\n' "$SHA" > "$STAGE/executor.sha256"
echo V360_EXECUTOR_SHA256="$SHA"
echo V360_DEPLOY_NAME="$NAME"
echo V360_STAGE_READY=TRUE
