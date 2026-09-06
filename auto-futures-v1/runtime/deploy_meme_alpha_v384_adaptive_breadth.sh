#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V384_ADAPTIVE=DEFER_NOT_ROOT'; exit 0; }

APP=/opt/meme-alpha/app
SCANNER="$APP/src/scanner.js"
BACKUP_ROOT=/opt/meme-alpha/backups
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/v384_adaptive_$TS"
LOCK=/tmp/meme-alpha-v384-adaptive.lock

exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V384_ADAPTIVE=DEFER_LOCK_BUSY'; exit 0; fi
[[ -f "$SCANNER" ]] || { echo 'MEME_V384_ADAPTIVE=DEFER_SCANNER_MISSING'; exit 0; }

if grep -q 'V384_ADAPTIVE_OPPORTUNITY_QUEUE' "$SCANNER"; then
  systemctl is-active --quiet meme-alpha-paper.service || systemctl restart meme-alpha-paper.service
  echo 'MEME_V384_ADAPTIVE=ALREADY_ACTIVE'
  exit 0
fi

mkdir -p "$BACKUP"
cp -a "$SCANNER" "$BACKUP/scanner.js"
TMP="$(mktemp /tmp/meme-alpha-v384-scanner.XXXXXX)"
cp -a "$SCANNER" "$TMP"

python3 - "$TMP" <<'PY'
from pathlib import Path
import sys,re
p=Path(sys.argv[1]); s=p.read_text()

# Increase only throughput budgets. Hard safety predicates are not modified.
s=re.sub(r"const MAX_SELLABILITY_CHECKS_V216=\d+;[^\n]*",
         "const MAX_SELLABILITY_CHECKS_V216=12; // V384_ADAPTIVE_OPPORTUNITY_QUEUE: bounded sellability budget",
         s, count=1)

# Replace the fixed top-N bottleneck with top-priority + rotating opportunity coverage.
pat=r"const baseDeep = preliminary\.slice\(0,\s*\d+\);[^\n]*\nconst baseMints = new Set\(baseDeep\.map\(x => x\.result\?\.mint\)\);"
rep="""// V384_ADAPTIVE_OPPORTUNITY_QUEUE
// Always inspect the strongest candidates, then rotate through the rest so every
// preliminary candidate gets repeated opportunities over successive cycles without
// forcing all network-heavy checks into one cycle.
const V384_TOP_PRIORITY = Math.min(24, preliminary.length);
const V384_ROTATING_BUDGET = Math.min(40, Math.max(0, preliminary.length - V384_TOP_PRIORITY));
const V384_TAIL = preliminary.slice(V384_TOP_PRIORITY);
const V384_BUCKET = Math.max(1, V384_TAIL.length);
const V384_OFFSET = V384_TAIL.length ? Math.floor(Date.now() / 30000) % V384_BUCKET : 0;
const V384_ROTATED = V384_TAIL.length ? [...V384_TAIL.slice(V384_OFFSET), ...V384_TAIL.slice(0, V384_OFFSET)] : [];
const baseDeep = [...preliminary.slice(0, V384_TOP_PRIORITY), ...V384_ROTATED.slice(0, V384_ROTATING_BUDGET)];
const baseMints = new Set(baseDeep.map(x => x.result?.mint));"""
s,n=re.subn(pat,rep,s,count=1)
if n!=1: raise SystemExit('PATCH_MISMATCH_BASE_DEEP')

# Meme/launchpad reserve is additional, bounded and deduplicated.
s=re.sub(r"const extraMeme = preliminary\n\s*\.slice\(\d+\)",
         "const extraMeme = preliminary\n  .slice(V384_TOP_PRIORITY)",s,count=1)
s=re.sub(r"\n\s*\.slice\(0,\s*\d+\);\nconst deep = \[\.\.\.baseDeep, \.\.\.extraMeme\];",
         "\n  .slice(0, 16);\nconst deep = [...baseDeep, ...extraMeme.filter(x=>!baseMints.has(x.result?.mint))];",
         s,count=1)

p.write_text(s)
PY

node --check "$TMP"
grep -q 'V384_ADAPTIVE_OPPORTUNITY_QUEUE' "$TMP"
grep -q 'MAX_SELLABILITY_CHECKS_V216=12' "$TMP"
grep -q 'V384_ROTATING_BUDGET' "$TMP"

# Verify the hard safety contract is still present exactly as a fail-closed gate.
grep -q 'securityDecision' "$TMP"
grep -q 'holderClusterDecision' "$TMP"
grep -q 'NO_SELL_ROUTE' "$TMP"
grep -q 'TOKEN2022' "$TMP"
grep -q 'DEX_LIQUIDITY_FAIL' "$TMP"

owner="$(stat -c %U "$SCANNER")"; group="$(stat -c %G "$SCANNER")"; mode="$(stat -c %a "$SCANNER")"
install -o "$owner" -g "$group" -m "$mode" "$TMP" "$SCANNER"
rm -f "$TMP"
node --check "$SCANNER"
systemctl restart meme-alpha-paper.service
sleep 3
systemctl is-active --quiet meme-alpha-paper.service

echo 'MEME_V384_ADAPTIVE=ACTIVE topPriority=24 rotating=40 extraMeme=16 sellabilityChecks=12 hardSafety=UNCHANGED'
