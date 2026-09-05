#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC="$APP/ops/meme-alpha/micro-live/micro-live-executor-v218.js"
DST="$APP/src/micro-live-executor.js"
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.18 RUNTIME COHERENCE APPLY ==='
[ -f "$SRC" ] || { echo ABORT_V218_NOT_STAGED; exit 1; }
node --check "$SRC"
node "$SRC" --self-test | grep -q 'MICRO_EXECUTOR_V218_SELF_TEST=PASS'
# Apply holder fast-fail prerequisite if it has not been applied yet.
if ! grep -q 'HOLDER_FAST_FAIL_V215' "$APP/src/holder-cluster.js"; then
  echo APPLYING_V215_HOLDER_FASTFAIL_PREREQUISITE=TRUE
  bash "$APP/ops/meme-alpha/v215-root-apply-holder-fastfail.sh"
else
  echo V215_HOLDER_FASTFAIL=ALREADY_ACTIVE
fi
# Avoid changing live position-management semantics in the middle of a position.
python3 - <<'PY'
import json,sys
p='/var/lib/meme-alpha/data/micro-live/state.json'
try:s=json.load(open(p))
except FileNotFoundError:s={}
if s.get('position'):
 print('ABORT_LIVE_POSITION_OPEN='+str(s['position'].get('symbol','UNKNOWN')));sys.exit(2)
print('LIVE_POSITION=NONE')
PY
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v218-$STAMP
mkdir -p "$BACKUP"
cp -a "$DST" "$BACKUP/micro-live-executor.js"
rollback(){ rc=$?; echo "V218_ROLLBACK rc=$rc" >&2; cp -f "$BACKUP/micro-live-executor.js" "$DST" || true; systemctl restart meme-alpha-micro-live.service >/dev/null 2>&1 || true; exit "$rc"; }
trap rollback ERR
install -o root -g root -m 0644 "$SRC" "$DST"
systemctl restart meme-alpha-micro-live.service
sleep 3
systemctl is-active --quiet meme-alpha-micro-live.service
grep -q 'MICRO_LIVE_EXECUTOR_V218_COHERENT=STARTED' "$DST"
# Signer remains v7 and armed; no key material is displayed.
HEALTH=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close();print(json.dumps(r,separators=(',',':')))
PY
)
python3 - "$HEALTH" <<'PY'
import json,sys
r=json.loads(sys.argv[1]);assert r.get('ok') is True and r.get('version')=='7.0' and r.get('signingEnabled') is True and r.get('arbitraryRawSign') is False
print('SIGNER_V7_ACTIVE=TRUE');print('SIGNER_ARMED=TRUE');print('ARBITRARY_RAW_SIGN=FALSE')
PY
# Require fresh runtime artifacts after the faster holder pipeline.
python3 - <<'PY'
import json,os,time,sys
sig='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';gate='/opt/meme-alpha/app/runtime-status/micro-live-gate.json';trend='/opt/meme-alpha/app/runtime-status/trend-pulse.json'
deadline=time.time()+90;last=''
while time.time()<deadline:
 try:
  s=json.load(open(sig));g=json.load(open(gate));t=json.load(open(trend));sa=time.time()-os.path.getmtime(sig);ga=time.time()-os.path.getmtime(gate);ta=time.time()-os.path.getmtime(trend)
  last=f'signalAge={sa:.1f} gateAge={ga:.1f} trendAge={ta:.1f} allowed={g.get("allowed")} reasons={",".join(g.get("reasons") or []) or "NONE"}'
  if sa<45 and ga<45 and ta<10:
   print('RUNTIME_FRESHNESS_PASS=TRUE');print('SIGNAL_AGE_SEC=%.1f'%sa);print('GATE_AGE_SEC=%.1f'%ga);print('TREND_AGE_SEC=%.1f'%ta);print('GATE_ALLOWED='+str(g.get('allowed')).lower());print('GATE_REASONS='+(','.join(g.get('reasons') or []) or 'NONE'));sys.exit(0)
 except Exception as e:last=str(e)
 time.sleep(3)
print('V218_RUNTIME_FRESHNESS_TIMEOUT '+last,file=sys.stderr);sys.exit(2)
PY

echo MICRO_EXECUTOR_V218_ACTIVE=TRUE
echo INITIAL_ENTRY_ALWAYS_PROBE_15_PCT=TRUE
echo SCALE_TIER_USES_FAST_TREND_SCORE=TRUE
echo ENTRY_SIGNAL_FRESHNESS_MAX_SEC=45
echo HARD_STALE_POSITION_EXIT_SEC=180
echo TP_SELL_IMPACT_CAP_PCT=2
echo GIVEBACK_SELL_IMPACT_CAP_PCT=3
echo CONFIRMED_BREAK_SELL_IMPACT_CAP_PCT=4
echo EMERGENCY_SELL_IMPACT_CAP_PCT=8
echo CAPITAL_STAGES_PRESERVED=15_35_65_94
echo SMART_PROFIT_EXIT_V210_PRESERVED=TRUE
echo V218_RUNTIME_COHERENCE_APPLY_PASS
echo "BACKUP=$BACKUP"
