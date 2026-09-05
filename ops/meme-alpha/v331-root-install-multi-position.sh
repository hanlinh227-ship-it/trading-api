#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V331_INSTALL_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app
SRC="$APP/runtime-status/v331-stage/micro-live-executor-v331-multi.js"
DST="$APP/src/micro-live-executor.js"
STATE=/var/lib/meme-alpha/data/micro-live/state.json
ARM=/etc/meme-alpha/micro-live-armed
SERVICE=meme-alpha-micro-live.service
EXPECTED=e80fe028b1db808a1b2a892efcb9087fd2330a79184dcb7b75b5feb79cbd7d90
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BKP="$APP/runtime-status/v331-root-backup-$STAMP"
mkdir -p "$BKP"
fail(){ echo "V331_INSTALL_FAIL=$1"; exit 1; }
[ -r "$SRC" ] || fail STAGED_SOURCE_MISSING
[ "$(sha256sum "$SRC"|awk '{print $1}')" = "$EXPECTED" ] || fail SOURCE_HASH_MISMATCH
/usr/bin/node --check "$SRC" || fail SOURCE_SYNTAX
/usr/bin/node "$SRC" --self-test | grep -q 'MICRO_EXECUTOR_V331_MULTI_SELF_TEST=PASS' || fail SOURCE_SELFTEST
cp -a "$DST" "$BKP/micro-live-executor.js"
[ -f "$STATE" ] && cp -a "$STATE" "$BKP/state.json" || true
cp -a "$ARM" "$BKP/micro-live-armed"
rollback(){
  rc=$?
  [ "$rc" -eq 0 ] && return
  echo V331_ROOT_ROLLBACK_START=TRUE
  cp -a "$BKP/micro-live-executor.js" "$DST" || true
  cp -a "$BKP/micro-live-armed" "$ARM" || true
  # Convert current multi state back to legacy shape if possible; disarmed mode guarantees no new buys during install.
  if [ -f "$STATE" ]; then
    runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE' || true
const fs=require('fs'),p=process.argv[2];try{const s=JSON.parse(fs.readFileSync(p,'utf8'));if(Array.isArray(s.positions)){if(s.positions.length>1)throw new Error('ROLLBACK_MULTI_GT1');s.position=s.positions[0]||null;delete s.positions;s.version='2.10.0';const t=p+'.rollback.tmp';fs.writeFileSync(t,JSON.stringify(s,null,2));fs.renameSync(t,p)}}catch(e){console.error(e.message);process.exit(1)}
NODE
  fi
  systemctl restart "$SERVICE" || true
  echo V331_ROOT_ROLLBACK_DONE=TRUE
}
trap rollback EXIT

# Fail-close entries during migration while exits remain available after service starts.
printf 'ARMED=NO\n' > "$ARM"
runuser -u meme-alpha -- /usr/bin/node - <<'NODE' || true
const fs=require('fs'),p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json';try{const g=JSON.parse(fs.readFileSync(p,'utf8'));g.allowed=false;g.reasons=[...new Set([...(g.reasons||[]),'V331_DEPLOYMENT_MIGRATION'])];fs.writeFileSync(p,JSON.stringify(g,null,2))}catch{}
NODE
systemctl stop "$SERVICE"

# Offline, deterministic legacy -> array migration. No network or orders.
runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),p=process.argv[2];let s={};try{s=JSON.parse(fs.readFileSync(p,'utf8'))}catch{};if(!Array.isArray(s.positions))s.positions=s.position?[s.position]:[];else if(s.position&&!s.positions.some(x=>x?.mint===s.position?.mint))throw new Error('LEGACY_POSITION_CONFLICT');delete s.position;const seen=new Set();for(const x of s.positions){if(!x?.mint||seen.has(x.mint))throw new Error('POSITION_MIGRATION_INVALID');seen.add(x.mint)}s.version='3.31.0-multi';s.manageCursor=Number.isFinite(Number(s.manageCursor))?Math.max(0,Math.floor(Number(s.manageCursor))):0;const t=p+'.v331.tmp';fs.mkdirSync(require('path').dirname(p),{recursive:true});fs.writeFileSync(t,JSON.stringify(s,null,2));fs.renameSync(t,p);console.log('MIGRATED_POSITIONS='+s.positions.length)
NODE

install -o root -g root -m 0644 "$SRC" "$DST"
systemctl start "$SERVICE"
sleep 7
systemctl is-active --quiet "$SERVICE" || fail SERVICE_NOT_ACTIVE
[ "$(pgrep -af '/opt/meme-alpha/app/src/micro-live-executor.js'|wc -l|tr -d ' ')" -eq 1 ] || fail EXECUTOR_PROCESS_COUNT
/usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));if(s.version!=='3.31.0-multi'||!Array.isArray(s.positions))throw new Error('STATE_NOT_MULTI');console.log(`MULTI_STATE_OK positions=${s.positions.length} mints=${s.positions.map(x=>x.mint).join(',')}`)
NODE
cp -a "$BKP/micro-live-armed" "$ARM"
echo V331_MULTI_POSITION_PRODUCTION_ACTIVE=TRUE
trap - EXIT
