#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V383_SCANNER=DEFER_NOT_ROOT'; exit 0; }

APP=/opt/meme-alpha/app
SCANNER="$APP/src/scanner.js"
BACKUP_ROOT=/opt/meme-alpha/backups
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/v383_scanner_$TS"
LOCK=/tmp/meme-alpha-v383-scanner.lock

exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V383_SCANNER=DEFER_LOCK_BUSY'; exit 0; fi
[[ -f "$SCANNER" ]] || { echo 'MEME_V383_SCANNER=DEFER_SCANNER_MISSING'; exit 0; }

# Idempotent: marker means the breadth-only patch is already active.
if grep -q 'V383_SAFE_BREADTH_EXPANSION' "$SCANNER"; then
  systemctl is-active --quiet meme-alpha-paper.service || systemctl restart meme-alpha-paper.service
  echo 'MEME_V383_SCANNER=ALREADY_ACTIVE'
  exit 0
fi

mkdir -p "$BACKUP"
cp -a "$SCANNER" "$BACKUP/scanner.js"
TMP="$(mktemp /tmp/meme-alpha-v383-scanner.XXXXXX)"
cp -a "$SCANNER" "$TMP"

python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
repls=[
("const MAX_SELLABILITY_CHECKS_V216=4; // V381 verify more actionable coins each cycle",
 "const MAX_SELLABILITY_CHECKS_V216=8; // V383_SAFE_BREADTH_EXPANSION: verify more actionable coins without weakening hard safety"),
("const baseDeep = preliminary.slice(0, 12);",
 "const baseDeep = preliminary.slice(0, 36); // V383_SAFE_BREADTH_EXPANSION"),
("const extraMeme = preliminary\n  .slice(20)",
 "const extraMeme = preliminary\n  .slice(12)"),
("  .slice(0, 4);\nconst deep = [...baseDeep, ...extraMeme];",
 "  .slice(0, 12);\nconst deep = [...baseDeep, ...extraMeme];")
]
for old,new in repls:
    if old not in s:
        raise SystemExit(f'PATCH_MISMATCH: {old[:80]}')
    s=s.replace(old,new,1)
p.write_text(s)
PY

node --check "$TMP"
grep -q 'V383_SAFE_BREADTH_EXPANSION' "$TMP"
grep -q 'MAX_SELLABILITY_CHECKS_V216=8' "$TMP"
grep -q 'preliminary.slice(0, 36)' "$TMP"
grep -q 'slice(0, 12)' "$TMP"

owner="$(stat -c %U "$SCANNER")"; group="$(stat -c %G "$SCANNER")"; mode="$(stat -c %a "$SCANNER")"
install -o "$owner" -g "$group" -m "$mode" "$TMP" "$SCANNER"
rm -f "$TMP"
node --check "$SCANNER"
systemctl restart meme-alpha-paper.service
sleep 3
systemctl is-active --quiet meme-alpha-paper.service

# Hard safety contract must remain present after breadth expansion.
grep -q "securityDecision" "$SCANNER"
grep -q "holderClusterDecision" "$SCANNER"
grep -q "NO_SELL_ROUTE" "$SCANNER"
grep -q "TOKEN2022" "$SCANNER"

echo 'MEME_V383_SCANNER=ACTIVE baseDeep=36 extraMeme=12 sellabilityChecks=8 hardSafety=UNCHANGED'
