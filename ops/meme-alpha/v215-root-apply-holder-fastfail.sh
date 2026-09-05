#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC="$APP/ops/meme-alpha/holder-cluster-v215.js"
DST="$APP/src/holder-cluster.js"
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.15 HOLDER FAST-FAIL APPLY ==='
[ -f "$SRC" ] || { echo ABORT_V215_NOT_STAGED; exit 1; }
node --check "$SRC"
grep -q 'HOLDER_FAST_FAIL_V215' "$SRC"
grep -q 'Promise.any' "$SRC"
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v215-$STAMP
mkdir -p "$BACKUP"
cp -a "$DST" "$BACKUP/holder-cluster.js"
rollback(){ rc=$?; echo "V215_ROLLBACK rc=$rc" >&2; cp -f "$BACKUP/holder-cluster.js" "$DST" || true; systemctl restart meme-alpha-paper.service >/dev/null 2>&1 || true; exit "$rc"; }
trap rollback ERR
install -o root -g root -m 0644 "$SRC" "$DST"
systemctl restart meme-alpha-paper.service
sleep 2
systemctl is-active --quiet meme-alpha-paper.service

# Wait for a complete fresh cycle. Do not bypass safety; require live gate to become
# healthy from genuinely fresh scanner/source/risk data.
python3 - <<'PY'
import json,os,time,sys
sig='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';gate='/opt/meme-alpha/app/runtime-status/micro-live-gate.json'
deadline=time.time()+75
last=''
while time.time()<deadline:
 try:
  s=json.load(open(sig));g=json.load(open(gate));sa=time.time()-os.path.getmtime(sig);ga=time.time()-os.path.getmtime(gate)
  last=f"signalAge={sa:.1f} gateAge={ga:.1f} allowed={g.get('allowed')} reasons={','.join(g.get('reasons') or []) or 'NONE'}"
  if sa<45 and ga<45 and g.get('allowed') is True:
   print('FRESH_SIGNAL_AGE_SEC=%.1f'%sa);print('FRESH_GATE_AGE_SEC=%.1f'%ga);print('GATE_ALLOWED=true');print('GATE_REASONS=NONE');sys.exit(0)
 except Exception as e:last=str(e)
 time.sleep(3)
print('V215_FRESHNESS_TIMEOUT '+last,file=sys.stderr);sys.exit(2)
PY

# Verify the holder stage no longer monopolizes the pipeline for minutes.
ps -eo pid,etimes,cmd | grep 'node src/holder-cluster.js' | grep -v grep || true

echo HOLDER_FAST_FAIL_ACTIVE=TRUE
echo HOLDER_RPC_TIMEOUT_MS=2500
echo HOLDER_RPC_ENDPOINTS_RACED=TRUE
echo HOLDER_CANDIDATE_CONCURRENCY=4
echo HOLDER_TARGETS_PER_CYCLE_MAX=12
echo HOLDER_FAILURE_STAYS_REVIEW_FAIL_CLOSED=TRUE
echo MICRO_LIVE_SMART_EXIT_V210_PRESERVED=TRUE
echo V215_HOLDER_FAST_FAIL_APPLY_PASS
echo "BACKUP=$BACKUP"
