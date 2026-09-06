#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SCANNER_SRC="$APP/ops/meme-alpha/scanner-v216-fast.js"
SCANNER_DST="$APP/src/scanner.js"
HOLDER_SRC="$APP/ops/meme-alpha/holder-cluster-v215.js"
HOLDER_DST="$APP/src/holder-cluster.js"
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.16 FAST PIPELINE APPLY ==='
[ -f "$SCANNER_SRC" ] || { echo ABORT_SCANNER_V216_NOT_STAGED; exit 1; }
[ -f "$HOLDER_SRC" ] || { echo ABORT_HOLDER_V215_NOT_STAGED; exit 1; }
node --check "$SCANNER_SRC"
node --check "$HOLDER_SRC"
grep -q 'SCANNER_FAST_PIPELINE_V216' "$SCANNER_SRC"
grep -q 'HOLDER_FAST_FAIL_V215' "$HOLDER_SRC"

STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v216-$STAMP
mkdir -p "$BACKUP"
cp -a "$SCANNER_DST" "$BACKUP/scanner.js"
cp -a "$HOLDER_DST" "$BACKUP/holder-cluster.js"
START_EPOCH=$(date +%s)
rollback(){
 rc=$?; echo "V216_ROLLBACK rc=$rc" >&2
 cp -f "$BACKUP/scanner.js" "$SCANNER_DST" || true
 cp -f "$BACKUP/holder-cluster.js" "$HOLDER_DST" || true
 systemctl restart meme-alpha-paper.service >/dev/null 2>&1 || true
 exit "$rc"
}
trap rollback ERR

install -o root -g root -m 0644 "$SCANNER_SRC" "$SCANNER_DST"
install -o root -g root -m 0644 "$HOLDER_SRC" "$HOLDER_DST"
systemctl restart meme-alpha-paper.service
sleep 2
systemctl is-active --quiet meme-alpha-paper.service

python3 - "$START_EPOCH" <<'PY'
import json,os,time,sys
start=float(sys.argv[1]);sig='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';gate='/opt/meme-alpha/app/runtime-status/micro-live-gate.json';scan='/var/lib/meme-alpha/data/paper/scanner-latest.json';deadline=time.time()+120;last=''
while time.time()<deadline:
 try:
  sm=os.path.getmtime(sig);gm=os.path.getmtime(gate);xm=os.path.getmtime(scan)
  sa=time.time()-sm;ga=time.time()-gm;xa=time.time()-xm
  s=json.load(open(sig));g=json.load(open(gate));x=json.load(open(scan))
  last=f"scanAge={xa:.1f} signalAge={sa:.1f} gateAge={ga:.1f} allowed={g.get('allowed')} reasons={','.join(g.get('reasons') or []) or 'NONE'}"
  if sm>=start and gm>=start and xm>=start and sa<45 and ga<45 and xa<45:
   elapsed=time.time()-start
   print('FIRST_FRESH_FULL_CYCLE_SEC=%.1f'%elapsed)
   print('FRESH_SCANNER_AGE_SEC=%.1f'%xa)
   print('FRESH_SIGNAL_AGE_SEC=%.1f'%sa)
   print('FRESH_GATE_AGE_SEC=%.1f'%ga)
   print('DISCOVERED='+str(x.get('discovered')))
   print('GATE_ALLOWED='+str(bool(g.get('allowed'))).lower())
   print('GATE_REASONS='+(','.join(g.get('reasons') or []) or 'NONE'))
   print('FRESH_PIPELINE=TRUE')
   sys.exit(0)
 except Exception as e:last=str(e)
 time.sleep(2)
print('V216_FRESH_PIPELINE_TIMEOUT '+last,file=sys.stderr);sys.exit(2)
PY

systemctl is-active --quiet meme-alpha-trend-pulse.service
systemctl is-active --quiet meme-alpha-micro-live.service
systemctl is-active --quiet meme-alpha-signer.service

grep -q 'MICRO_LIVE_EXECUTOR_V210' "$APP/src/micro-live-executor.js" || grep -q 'SMART_PARTIAL_TP' "$APP/src/micro-live-executor.js"

echo SCANNER_FAST_PIPELINE_ACTIVE=TRUE
echo SCANNER_DEX_BATCH=TRUE
echo SCANNER_SELLABILITY_BUDGET_PER_CYCLE=8
echo HOLDER_FAST_FAIL_ACTIVE=TRUE
echo HOLDER_RPC_TIMEOUT_MS=2500
echo HOLDER_CONCURRENCY=4
echo V210_SMART_PROFIT_EXIT_PRESERVED=TRUE
echo HARD_SAFETY_GATES_PRESERVED=TRUE
echo V216_FAST_PIPELINE_APPLY_PASS
echo "BACKUP=$BACKUP"
