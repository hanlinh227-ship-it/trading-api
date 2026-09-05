#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RSTATE="$APP/runtime-status/new-listing-radar.json"
RLOG="$APP/runtime-status/new-listing-radar-runtime.log"
SIG="$APP/runtime-status/signal-snapshot.json"
RUN="$APP/run-paper.sh"
SCANNER="$APP/src/scanner.js"

echo '=== V322 FINAL ALL COMPONENTS AUDIT ==='
sudo -n /bin/systemctl is-active meme-alpha-paper.service

check_proc(){
  local label="$1" pattern="$2"
  if pgrep -af "$pattern" | grep -v 'v321-final-all-components-audit' >/dev/null; then
    echo "$label=ACTIVE"
    pgrep -af "$pattern" | grep -v 'v321-final-all-components-audit' | head -5
  else
    echo "$label=INACTIVE"
    exit 21
  fi
}

check_proc PAPER_RUNNER '/opt/meme-alpha/app/run-paper.sh'
check_proc TREND_PULSE '/opt/meme-alpha/app/src/trend-pulse.js'
check_proc MICRO_LIVE_EXECUTOR '/opt/meme-alpha/app/src/micro-live-executor.js'
check_proc SIGNER '/opt/meme-alpha-signer/ready_signer.py'

[ -r "$RUN" ] && grep -q 'NEW_LISTING_RADAR_LOOP_V312' "$RUN" || { echo RADAR_LOOP_NOT_INSTALLED; exit 22; }
[ -r "$SCANNER" ] && grep -q 'NEW_LISTING_RADAR_V312' "$SCANNER" || { echo SCANNER_RADAR_INTEGRATION_MISSING; exit 23; }
/usr/bin/node --check "$SCANNER"

radar_stamp(){
  /usr/bin/node - "$RSTATE" <<'NODE'
const fs=require('fs');
try{const r=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(r.updatedAt||''))}catch{process.exit(2)}
NODE
}

R1=$(radar_stamp)
[ -n "$R1" ] || { echo RADAR_TIMESTAMP_MISSING; exit 24; }
echo "RADAR_STAMP_1=$R1"
sleep 7
R2=$(radar_stamp)
echo "RADAR_STAMP_2=$R2"
[ -n "$R2" ] && [ "$R2" != "$R1" ] || { echo RADAR_LOOP_NOT_ADVANCING; tail -80 "$RLOG" 2>/dev/null || true; exit 25; }

echo NEW_LISTING_RADAR=ACTIVE_CYCLING

/usr/bin/node - "$RSTATE" "$SIG" <<'NODE'
const fs=require('fs');
const [radarPath,sigPath]=process.argv.slice(2);
function read(p){return JSON.parse(fs.readFileSync(p,'utf8'))}
const now=Date.now();
const r=read(radarPath);
const s=read(sigPath);
const rAge=(now-Date.parse(r.updatedAt||0))/1000;
const st=String(s.timestamp||s.updatedAt||s.generatedAt||'');
const sAge=(now-Date.parse(st))/1000;
const h=s.sourceHealth||{};
console.log(`RADAR status=${r.status} ageSec=${rAge.toFixed(2)} feedMints=${Number(r.currentFeedMints||0)} candidates=${Array.isArray(r.candidates)?r.candidates.length:0} jupiterRecentOk=${r.jupiterRecentOk===true}`);
console.log(`SIGNAL ageSec=${sAge.toFixed(2)} source=${h.status||''} cache=${h.usingCache===true} candidates=${Array.isArray(s.candidates)?s.candidates.length:0}`);
if(r.status!=='HEALTHY'||!Number.isFinite(rAge)||rAge<0||rAge>15||Number(r.currentFeedMints||0)<=0||r.jupiterRecentOk!==true) process.exit(31);
if(!Number.isFinite(sAge)||sAge<0||sAge>35||h.status!=='HEALTHY'||h.usingCache===true) process.exit(32);
NODE

echo SCANNER_INTEGRATION=ACTIVE

echo V322_ALL_RUNTIME_COMPONENTS_ACTIVE_PASS
