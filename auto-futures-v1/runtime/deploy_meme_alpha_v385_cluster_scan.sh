#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V385_CLUSTER=DEFER_NOT_ROOT'; exit 0; }

APP=/opt/meme-alpha/app
SCANNER="$APP/src/scanner.js"
BACKUP_ROOT=/opt/meme-alpha/backups
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/v385_cluster_$TS"
LOCK=/tmp/meme-alpha-v385-cluster.lock

exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V385_CLUSTER=DEFER_LOCK_BUSY'; exit 0; fi
[[ -f "$SCANNER" ]] || { echo 'MEME_V385_CLUSTER=DEFER_SCANNER_MISSING'; exit 0; }

if grep -q 'V385_SEQUENTIAL_CLUSTER_SCAN' "$SCANNER"; then
  systemctl is-active --quiet meme-alpha-paper.service || systemctl restart meme-alpha-paper.service
  echo 'MEME_V385_CLUSTER=ALREADY_ACTIVE'
  exit 0
fi

# Ensure the v3.84 adaptive block exists so v3.85 can replace it deterministically.
if ! grep -q 'V384_ADAPTIVE_OPPORTUNITY_QUEUE' "$SCANNER"; then
  V384="/opt/trading/trading-api/auto-futures-v1/runtime/deploy_meme_alpha_v384_adaptive_breadth.sh"
  [[ -f "$V384" ]] && /bin/bash "$V384" >/tmp/meme_v385_prepare_v384.out 2>&1 || true
fi

grep -q 'V384_ADAPTIVE_OPPORTUNITY_QUEUE' "$SCANNER" || { echo 'MEME_V385_CLUSTER=DEFER_V384_BASE_MISSING'; exit 0; }

mkdir -p "$BACKUP"
cp -a "$SCANNER" "$BACKUP/scanner.js"
TMP="$(mktemp /tmp/meme-alpha-v385-scanner.XXXXXX)"
cp -a "$SCANNER" "$TMP"

python3 - "$TMP" <<'PY'
from pathlib import Path
import sys,re
p=Path(sys.argv[1]); s=p.read_text()

# Keep expensive sellability verification bounded even while coverage becomes broader.
s,n=re.subn(r"const MAX_SELLABILITY_CHECKS_V216=\d+;[^\n]*",
            "const MAX_SELLABILITY_CHECKS_V216=8; // V385_SEQUENTIAL_CLUSTER_SCAN: bounded expensive checks per cluster",
            s,count=1)
if n!=1: raise SystemExit('PATCH_MISMATCH_SELLABILITY')

pat=r"// V384_ADAPTIVE_OPPORTUNITY_QUEUE.*?const baseMints = new Set\(baseDeep\.map\(x => x\.result\?\.mint\)\);"
rep="""// V385_SEQUENTIAL_CLUSTER_SCAN
// Process one bounded cluster at a time. Each cycle gets a small priority reserve plus
// a rotating contiguous cluster from the whole preliminary universe. This prevents
// the top-ranked names from monopolising deep checks while keeping API load bounded.
const V385_PRIORITY_RESERVE = Math.min(8, preliminary.length);
const V385_CLUSTER_SIZE = Math.min(36, Math.max(0, preliminary.length - V385_PRIORITY_RESERVE));
const V385_TAIL = preliminary.slice(V385_PRIORITY_RESERVE);
const V385_BUCKET_COUNT = Math.max(1, Math.ceil(V385_TAIL.length / Math.max(1, V385_CLUSTER_SIZE)));
const V385_BUCKET_INDEX = V385_TAIL.length ? Math.floor(Date.now() / 30000) % V385_BUCKET_COUNT : 0;
const V385_START = V385_BUCKET_INDEX * V385_CLUSTER_SIZE;
const V385_CLUSTER = V385_TAIL.slice(V385_START, V385_START + V385_CLUSTER_SIZE);
const baseDeep = [...preliminary.slice(0, V385_PRIORITY_RESERVE), ...V385_CLUSTER];
const baseMints = new Set(baseDeep.map(x => x.result?.mint));"""
s,n=re.subn(pat,rep,s,count=1,flags=re.S)
if n!=1: raise SystemExit('PATCH_MISMATCH_V384_BLOCK')

# Make the meme reserve follow the currently selected cluster rather than reopening a huge tail.
s=re.sub(r"const extraMeme = preliminary\n\s*\.slice\([^\n]+\)",
         "const extraMeme = V385_CLUSTER",s,count=1)
s=re.sub(r"\n\s*\.slice\(0,\s*16\);\nconst deep = \[\.\.\.baseDeep, \.\.\.extraMeme\.filter\(x=>!baseMints\.has\(x\.result\?\.mint\)\)\];",
         "\n  .slice(0, 8);\nconst deep = [...baseDeep, ...extraMeme.filter(x=>!baseMints.has(x.result?.mint))];",
         s,count=1)

p.write_text(s)
PY

node --check "$TMP"
grep -q 'V385_SEQUENTIAL_CLUSTER_SCAN' "$TMP"
grep -q 'V385_CLUSTER_SIZE' "$TMP"
grep -q 'MAX_SELLABILITY_CHECKS_V216=8' "$TMP"

# Hard safety remains fail-closed. v3.85 changes only scheduling/throughput.
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

echo 'MEME_V385_CLUSTER=ACTIVE priority=8 cluster=36 cycleBucketSec=30 sellabilityChecks=8 hardSafety=UNCHANGED'
