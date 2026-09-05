#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STATE=/var/lib/meme-alpha/data/micro-live/state.json
printf '%s\n' '=== V354 RUNTIME INTEGRITY AUDIT ==='
printf 'HOST=%s\n' "$(hostname)"
printf '%s\n' '--- services ---'
for s in meme-alpha-micro-live.service meme-alpha-paper.service meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service meme-alpha-signer.service; do
  printf '%s=%s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null || true)"
done
printf '%s\n' '--- executor process ---'
pgrep -af '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true
printf 'EXECUTOR_COUNT=%s\n' "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)"
printf '%s\n' '--- state path/permissions ---'
namei -l "$STATE" || true
stat -c 'STATE_STAT owner=%U group=%G mode=%a size=%s mtime=%y' "$STATE" 2>/dev/null || echo STATE_STAT=MISSING
if [ -r "$STATE" ]; then
  node - "$STATE" <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
console.log('RUNNER_CAN_READ_STATE=TRUE');
console.log('STATE_VERSION='+(s.version||''));
console.log('OPEN_POSITIONS='+((s.positions||[]).length));
console.log('POSITION_MINTS='+JSON.stringify((s.positions||[]).map(x=>x.mint).sort()));
NODE
else
  echo RUNNER_CAN_READ_STATE=FALSE
fi
printf '%s\n' '--- executor recent log evidence ---'
journalctl -u meme-alpha-micro-live.service --since '-10 min' --no-pager -o cat 2>/dev/null | tail -n 120 || true
printf '%s\n' '--- whale flow recent log evidence ---'
journalctl -u meme-alpha-whale-flow.service --since '-10 min' --no-pager -o cat 2>/dev/null | tail -n 120 || true
printf '%s\n' '--- runtime snapshots ---'
for f in signal-snapshot.json micro-live-gate.json realtime-pool-pulse.json whale-flow-intel.json; do
  p="$APP/runtime-status/$f"
  if [ -f "$p" ]; then
    node - "$p" "$f" <<'NODE'
const fs=require('fs');const j=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const name=process.argv[3];
const t=Date.parse(j.updatedAt||j.timestamp||0),age=Number.isFinite(t)?(Date.now()-t)/1000:NaN;
console.log(name+'_STATUS='+(j.status??j.allowed??''));
console.log(name+'_AGE_SEC='+(Number.isFinite(age)?age.toFixed(2):'NA'));
console.log(name+'_ROWS='+((j.rows||j.candidates||[]).length));
if(name==='signal-snapshot.json'){
  const rows=j.candidates||[]; const eligible=rows.filter(x=>x?.securityDecision==='PASS'&&x?.holderClusterDecision==='PASS');
  console.log('SIGNAL_SECURITY_HOLDER_PASS='+eligible.length);
}
NODE
  fi
done
printf '%s\n' '--- source ownership ---'
for p in "$APP/src/micro-live-executor.js" "$APP/src/whale-flow-intel.js" "$APP/src/realtime-pool-pulse.js" "$APP/run-paper.sh"; do stat -c '%n owner=%U group=%G mode=%a sha=%s' "$p" 2>/dev/null || true; done
printf '%s\n' 'V354_RUNTIME_INTEGRITY_AUDIT=COMPLETE'
