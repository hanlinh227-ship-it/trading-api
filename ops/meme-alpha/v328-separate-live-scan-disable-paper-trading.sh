#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUN="$APP/run-paper.sh"
SERVICE=meme-alpha-paper.service
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BKP="$APP/runtime-status/v328-backup-$STAMP"
mkdir -p "$BKP"

fail(){ echo "V328_FAIL=$1"; exit 1; }
[ -r "$RUN" ] && [ -w "$RUN" ] || fail RUN_PAPER_NOT_WRITABLE
cp -p "$RUN" "$BKP/run-paper.sh"

echo "V328_BACKUP=$BKP"
rollback(){
  echo V328_ROLLBACK_START=TRUE
  local t="$APP/.run-paper-v328-rollback.$$.sh"
  cp "$BKP/run-paper.sh" "$t" || true
  chmod 775 "$t" || true
  mv -f "$t" "$RUN" || true
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo V328_ROLLBACK_DONE=TRUE
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi' EXIT

TMP="$APP/.run-paper-v328.$$.sh"
python3 - "$RUN" > "$TMP" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()

if 'V328_LIVE_SCAN_ONLY' not in s:
    anchor='cd /opt/meme-alpha/app || exit 1\n'
    if s.count(anchor)!=1: raise SystemExit('V328_CD_ANCHOR')
    block=r'''

# V328_LIVE_SCAN_ONLY
# The legacy systemd unit is still named meme-alpha-paper.service for compatibility,
# but it now performs discovery/risk/signal generation only. PAPER BUY/SELL execution
# is disabled and the old demo ledger is archived once by the service user.
LIVE_SCAN_ONLY=1
init_live_scan_only() {
  /usr/bin/node - <<'NODE_V328_INIT' 2>/dev/null || true
const fs=require('fs'),path=require('path');
const data='/var/lib/meme-alpha/data/paper';
const marker=path.join(data,'.v328-live-scan-only');
const runtime='/opt/meme-alpha/app/runtime-status';
try{
  fs.mkdirSync(data,{recursive:true});
  if(!fs.existsSync(marker)){
    const stamp=new Date().toISOString().replace(/[:.]/g,'-');
    const arc=path.join(data,'demo-archive-'+stamp);
    fs.mkdirSync(arc,{recursive:true});
    for(const n of ['state.json','validation.json','stress-test.json','risk-state.json','reaction-telemetry.json']){
      const p=path.join(data,n); if(fs.existsSync(p)) try{fs.copyFileSync(p,path.join(arc,n))}catch{}
    }
    const neutral={version:'LIVE_SCAN_ONLY_V328',mode:'LIVE_SCAN_ONLY',startingEquitySol:1,equitySol:1,highWaterEquitySol:1,realizedPnlSol:0,unrealizedPnlSol:0,openPositions:[],trades:[],paperExecutionEnabled:false,resetAt:new Date().toISOString()};
    const sp=path.join(data,'state.json'),tmp=sp+'.v328.tmp';fs.writeFileSync(tmp,JSON.stringify(neutral,null,2));fs.renameSync(tmp,sp);
    fs.writeFileSync(marker,JSON.stringify({mode:'LIVE_SCAN_ONLY',paperExecutionEnabled:false,archivedTo:arc,createdAt:new Date().toISOString()},null,2));
  }
  const out={version:'3.28.0',timestamp:new Date().toISOString(),mode:'LIVE_SCAN_ONLY',paperExecutionEnabled:false,liveExecutionOwnedBy:'meme-alpha-micro-live.service',scannerEnabled:true,radarEnabled:true,legacyUnitName:'meme-alpha-paper.service'};
  const op=path.join(runtime,'execution-separation.json'),ot=op+'.tmp';fs.writeFileSync(ot,JSON.stringify(out,null,2));fs.renameSync(ot,op);try{fs.chmodSync(op,0o664)}catch{}
  for(const [name,obj] of [['validation.json',{version:'DISABLED_V328',timestamp:new Date().toISOString(),readinessStatus:'DISABLED_LIVE_ONLY',completedLifecycleTrades:0}],['stress-test.json',{version:'DISABLED_V328',timestamp:new Date().toISOString(),status:'DISABLED_LIVE_ONLY'}]]){
    const p=path.join(runtime,name),t=p+'.v328.tmp';fs.writeFileSync(t,JSON.stringify(obj,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}
  }
}catch(e){}
NODE_V328_INIT
}
init_live_scan_only
'''
    s=s.replace(anchor,anchor+block)

# Replace the old all-in-one paper cycle with a scan/safety/signal-only cycle.
old='  /usr/bin/npm run cycle5\n  rc=$?'
if old in s:
    new='''  # V328: live scanner pipeline only; intentionally excludes position.js, validation.js and stress-test.js.\n  /usr/bin/node src/scanner.js && \\\n  /usr/bin/node src/universe.js && \\\n  /usr/bin/node src/security.js && \\\n  /usr/bin/node src/token2022-audit.js && \\\n  /usr/bin/node src/holder-cluster.js && \\\n  /usr/bin/node src/persistence.js && \\\n  /usr/bin/node src/risk.js && \\\n  /usr/bin/node src/safe-signal-export.js && \\\n  /usr/bin/node src/micro-live-gate.js\n  rc=$?'''
    s=s.replace(old,new)
elif 'npm run cycle5' in s:
    raise SystemExit('V328_CYCLE5_UNEXPECTED')

# Remove fast PAPER position-management ticks between discovery cycles.
old='''    POS=$(open_positions_count)\n    if [ "$POS" -gt 0 ]; then\n      REM=$((GAP-ELAPSED))\n      SLEEP_SEC="$ACTIVE_POSITION_TICK_SEC"\n      if [ "$REM" -lt "$SLEEP_SEC" ]; then SLEEP_SEC="$REM"; fi\n      [ "$SLEEP_SEC" -gt 0 ] && sleep "$SLEEP_SEC"\n      echo "FAST_POSITION_TICK $(date -u +"%Y-%m-%dT%H:%M:%SZ") positions=$POS target=${ACTIVE_POSITION_TICK_SEC}s"\n      MEME_ALPHA_MANAGE_ONLY=1 /usr/bin/node src/position.js || echo "FAST_POSITION_TICK_FAILED"\n    else\n      REM=$((GAP-ELAPSED))\n      SLEEP_SEC="$IDLE_CHECK_SEC"\n      if [ "$REM" -lt "$SLEEP_SEC" ]; then SLEEP_SEC="$REM"; fi\n      [ "$SLEEP_SEC" -gt 0 ] && sleep "$SLEEP_SEC"\n      echo "FAST_IDLE_SKIP $(date -u +"%Y-%m-%dT%H:%M:%SZ") positions=0"\n    fi'''
if old in s:
    new='''    REM=$((GAP-ELAPSED))\n    SLEEP_SEC="$IDLE_CHECK_SEC"\n    if [ "$REM" -lt "$SLEEP_SEC" ]; then SLEEP_SEC="$REM"; fi\n    [ "$SLEEP_SEC" -gt 0 ] && sleep "$SLEEP_SEC"\n    echo "LIVE_SCAN_ONLY_WAIT $(date -u +"%Y-%m-%dT%H:%M:%SZ") paper_execution=disabled"'''
    s=s.replace(old,new)

sys.stdout.write(s)
PY

/bin/bash -n "$TMP" || fail RUN_PAPER_SYNTAX
chmod 775 "$TMP"
mv -f "$TMP" "$RUN"

# Static separation invariants before restart.
grep -q 'V328_LIVE_SCAN_ONLY' "$RUN" || fail MARKER_MISSING
grep -q 'paperExecutionEnabled:false' "$RUN" || fail DISABLE_MARKER_MISSING
if grep -q 'npm run cycle5' "$RUN"; then fail CYCLE5_STILL_ACTIVE; fi
if grep -E 'MEME_ALPHA_MANAGE_ONLY=1 .*src/position\.js|/usr/bin/node src/position\.js' "$RUN"; then fail PAPER_POSITION_EXECUTION_STILL_ACTIVE; fi
grep -q '/usr/bin/node src/scanner.js' "$RUN" || fail SCANNER_MISSING
grep -q '/usr/bin/node src/safe-signal-export.js' "$RUN" || fail SIGNAL_EXPORT_MISSING
grep -q '/usr/bin/node src/micro-live-gate.js' "$RUN" || fail GATE_MISSING
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=6' "$RUN" || fail FRESHNESS_GUARD_MISSING
grep -q 'new-listing-radar.js' "$RUN" || fail RADAR_LOOP_MISSING
echo V328_STATIC_SEPARATION=PASS

sudo -n /bin/systemctl restart "$SERVICE" || fail SERVICE_RESTART_FAILED
sleep 4
sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null || fail SERVICE_NOT_ACTIVE

# Verify separation marker is emitted by the service user.
SEP="$APP/runtime-status/execution-separation.json"
sep_ok=0
for i in $(seq 1 20); do
  sleep 1
  row=$(/usr/bin/node - "$SEP" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log([x.mode,x.paperExecutionEnabled,x.scannerEnabled,x.radarEnabled].join('|'))}catch{}
NODE
)
  if [ "$row" = 'LIVE_SCAN_ONLY|false|true|true' ]; then sep_ok=1; break; fi
done
[ "$sep_ok" -eq 1 ] || fail SEPARATION_MARKER_NOT_READY
echo "SEPARATION=$row"

# Signal must advance and remain healthy. This proves scanner -> signal -> gate still works without paper execution.
SIG="$APP/runtime-status/signal-snapshot.json"
first=$(/usr/bin/node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(x.timestamp||''))}catch{}
NODE
)
sig_ok=0
for i in $(seq 1 45); do
  sleep 2
  row=$(/usr/bin/node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const h=x.sourceHealth||{},t=String(x.timestamp||'');const age=(Date.now()-Date.parse(t))/1000;console.log([t,h.status||'',h.usingCache===true?'1':'0',Number.isFinite(age)?age.toFixed(2):'999',(x.candidates||[]).length].join('|'))}catch{}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r stamp health cache age count <<< "$row"
  if [ -n "$stamp" ] && [ "$stamp" != "$first" ] && [ "$health" = HEALTHY ] && [ "$cache" = 0 ]; then sig_ok=1; break; fi
done
[ "$sig_ok" -eq 1 ] || fail SIGNAL_DID_NOT_ADVANCE_HEALTHY
echo "SIGNAL_AFTER_SEPARATION=$row"

# Radar must still advance independently.
RAD="$APP/runtime-status/new-listing-radar.json"
r1=$(/usr/bin/node - "$RAD" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(x.updatedAt||''))}catch{}
NODE
)
sleep 10
r2=$(/usr/bin/node - "$RAD" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(x.updatedAt||''))}catch{}
NODE
)
[ -n "$r1" ] && [ -n "$r2" ] && [ "$r1" != "$r2" ] || fail RADAR_NOT_ADVANCING
echo "RADAR_ADVANCED=$r1->$r2"

# Ensure there is exactly one live executor and signer; do not touch them.
exec_count=$(pgrep -af '/opt/meme-alpha/app/src/micro-live-executor.js' | grep -v v328 | wc -l | tr -d ' ')
signer_count=$(pgrep -af '/opt/meme-alpha-signer/ready_signer.py' | grep -v v328 | wc -l | tr -d ' ')
[ "$exec_count" -eq 1 ] || fail "LIVE_EXECUTOR_COUNT_$exec_count"
[ "$signer_count" -eq 1 ] || fail "SIGNER_COUNT_$signer_count"
echo "LIVE_EXECUTOR_COUNT=$exec_count SIGNER_COUNT=$signer_count"

echo V328_LIVE_SCAN_ONLY_ACTIVE_PASS
trap - EXIT
