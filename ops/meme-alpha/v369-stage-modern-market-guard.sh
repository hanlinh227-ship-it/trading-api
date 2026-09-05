#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v369-stage"
DEPLOY="$APP/runtime-status/deploy-candidates"
NAME=micro-live-executor-v369-modern-market-guard.js
SRC="$APP/src/micro-live-executor.js"
OUT="$STAGE/$NAME"
STATE=/var/lib/meme-alpha/data/micro-live/state.json
mkdir -p "$STAGE" "$DEPLOY"

# Snapshot only structural state for post-deploy audit. Never mutate live state here.
/usr/bin/node - "$STATE" > "$STAGE/pre-state.json" <<'NODE'
const fs=require('fs');
const p=process.argv[2];
let s={};try{s=JSON.parse(fs.readFileSync(p,'utf8'))}catch(e){throw new Error('PRE_STATE_UNREADABLE')}
const positions=Array.isArray(s.positions)?s.positions:[];
const mints=positions.map(x=>x?.mint).filter(Boolean);
if(new Set(mints).size!==mints.length)throw new Error('PRE_STATE_DUPLICATE_MINT');
console.log(JSON.stringify({version:s.version||null,openPositions:positions.length,mints:mints.sort()}));
NODE

cp "$SRC" "$OUT"
python3 "$ROOT/ops/meme-alpha/v369-patch-modern-market-guard.py" "$OUT"
/usr/bin/node --check "$OUT"
TEST=$(/usr/bin/node "$OUT" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'MICRO_EXECUTOR_V369_MODERN_MARKET_GUARD_SELF_TEST=PASS'
echo "$TEST" | grep -q 'MODERN_INTEL_FRESHNESS_GUARD=TRUE'
echo "$TEST" | grep -q 'WHALE_ROW_TIMESTAMP_FRESHNESS=TRUE'
echo "$TEST" | grep -q 'EXIT_LIQUIDITY_ALLOCATION_CAP=TRUE'
echo "$TEST" | grep -q 'ENTRY_CIRCUIT_BREAKER=TRUE'
echo "$TEST" | grep -q 'RUG_SHIELD_EXPLICIT_SIGNALS=TRUE'
echo "$TEST" | grep -q 'TOKEN2022_DANGEROUS_EXTENSION_BLOCK=TRUE'
echo "$TEST" | grep -q 'EXITS_NOT_BLOCKED_BY_INTEL=TRUE'
echo "$TEST" | grep -q 'PROFIT_AWARE_WEAK_EXIT=TRUE'
echo "$TEST" | grep -q 'WINNER_ROTATION_PROTECTION=TRUE'
echo "$TEST" | grep -q 'SEVERE_TREND_BREAK_FULL_EXIT=KEPT'
echo "$TEST" | grep -q 'HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT'

install -m 0644 "$OUT" "$DEPLOY/$NAME"
SHA=$(sha256sum "$DEPLOY/$NAME" | awk '{print $1}')
printf '%s\n' "$NAME" > "$STAGE/deploy-name.txt"
printf '%s\n' "$SHA" > "$STAGE/executor.sha256"
echo V369_EXECUTOR_SHA256="$SHA"
echo V369_DEPLOY_NAME="$NAME"
echo V369_STAGE_READY=TRUE
