#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RSTATE="$APP/runtime-status/new-listing-radar.json"
SIG="$APP/runtime-status/signal-snapshot.json"

echo '=== V321 FINAL ALL COMPONENTS AUDIT ==='
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
check_proc NEW_LISTING_RADAR '/opt/meme-alpha/app/src/new-listing-radar.js'
check_proc TREND_PULSE '/opt/meme-alpha/app/src/trend-pulse.js'
check_proc MICRO_LIVE_EXECUTOR '/opt/meme-alpha/app/src/micro-live-executor.js'
check_proc SIGNER '/opt/meme-alpha-signer/ready_signer.py'

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
if(r.status!=='HEALTHY'||!Number.isFinite(rAge)||rAge<0||rAge>15||Number(r.currentFeedMints||0)<=0) process.exit(31);
if(!Number.isFinite(sAge)||sAge<0||sAge>35||h.status!=='HEALTHY'||h.usingCache===true) process.exit(32);
NODE

echo V321_ALL_RUNTIME_COMPONENTS_ACTIVE_PASS
