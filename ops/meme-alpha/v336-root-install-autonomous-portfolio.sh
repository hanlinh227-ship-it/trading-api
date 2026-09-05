#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V336_INSTALL_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v336-stage"
SRC="$STAGE/micro-live-executor-v336-autonomous.js"
DST="$APP/src/micro-live-executor.js"
STATE=/var/lib/meme-alpha/data/micro-live/state.json
ARM=/etc/meme-alpha/micro-live-armed
SERVICE=meme-alpha-micro-live.service
EXPECTED=608785762d5387b58a2bfb4adead1bf29e7cfe9c489472bf7013442a35ab21d2
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BKP="$APP/runtime-status/v336-root-backup-$STAMP"
mkdir -p "$BKP"
fail(){ echo "V336_INSTALL_FAIL=$1"; exit 1; }
[ -r "$SRC" ] || fail STAGED_SOURCE_MISSING
[ "$(sha256sum "$SRC"|awk '{print $1}')" = "$EXPECTED" ] || fail SOURCE_HASH_MISMATCH
/usr/bin/node --check "$SRC" || fail SOURCE_SYNTAX
/usr/bin/node "$SRC" --self-test | grep -q 'MICRO_EXECUTOR_V336_AUTONOMOUS_SELF_TEST=PASS' || fail SOURCE_SELFTEST
cp -a "$DST" "$BKP/micro-live-executor.js"
[ -f "$STATE" ] && cp -a "$STATE" "$BKP/state.json" || true
cp -a "$ARM" "$BKP/micro-live-armed"
rollback(){
  rc=$?
  [ "$rc" -eq 0 ] && return
  echo V336_ROOT_ROLLBACK_START=TRUE
  cp -a "$BKP/micro-live-executor.js" "$DST" || true
  [ -f "$BKP/state.json" ] && cp -a "$BKP/state.json" "$STATE" || true
  cp -a "$BKP/micro-live-armed" "$ARM" || true
  systemctl restart "$SERVICE" || true
  echo V336_ROOT_ROLLBACK_DONE=TRUE
}
trap rollback EXIT

# Freeze new BUYs only during replacement. Existing positions are preserved exactly.
printf 'ARMED=NO\n' > "$ARM"
runuser -u meme-alpha -- /usr/bin/node - <<'NODE' || true
const fs=require('fs'),p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json';try{const g=JSON.parse(fs.readFileSync(p,'utf8'));g.allowed=false;g.reasons=[...new Set([...(g.reasons||[]),'V336_AUTONOMOUS_DEPLOYMENT'])];fs.writeFileSync(p,JSON.stringify(g,null,2))}catch{}
NODE
systemctl stop "$SERVICE"

# Schema-compatible v3.31 -> v3.36 metadata migration; positions are not altered.
runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),path=require('path'),p=process.argv[2];let s={};try{s=JSON.parse(fs.readFileSync(p,'utf8'))}catch{};if(!Array.isArray(s.positions))s.positions=s.position?[s.position]:[];delete s.position;const seen=new Set();for(const x of s.positions){if(!x?.mint||seen.has(x.mint))throw new Error('POSITION_STATE_INVALID');seen.add(x.mint)};s.version='3.36.0-autonomous';if(!s.autonomy||typeof s.autonomy!=='object')s.autonomy={};const t=p+'.v336.tmp';fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(t,JSON.stringify(s,null,2));fs.renameSync(t,p);console.log('PRESERVED_POSITIONS='+s.positions.length);console.log('PRESERVED_MINTS='+s.positions.map(x=>x.mint).join(','));
NODE

install -o root -g root -m 0644 "$SRC" "$DST"
systemctl start "$SERVICE"
sleep 8
systemctl is-active --quiet "$SERVICE" || fail SERVICE_NOT_ACTIVE
[ "$(pgrep -af '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js'|wc -l|tr -d ' ')" -eq 1 ] || fail EXECUTOR_PROCESS_COUNT
grep -q 'MICRO_LIVE_EXECUTOR_V336_AUTONOMOUS_PORTFOLIO=STARTED' "$DST" || fail VERSION_MARKER_MISSING
/usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));if(s.version!=='3.36.0-autonomous'||!Array.isArray(s.positions))throw new Error('STATE_NOT_V336');const seen=new Set();for(const x of s.positions){if(!x?.mint||seen.has(x.mint))throw new Error('STATE_POSITION_CONFLICT');seen.add(x.mint)}console.log(`AUTONOMOUS_STATE_OK positions=${s.positions.length} mints=${s.positions.map(x=>x.mint).join(',')}`)
NODE
cp -a "$BKP/micro-live-armed" "$ARM"
sleep 2
echo V336_AUTONOMOUS_PORTFOLIO_PRODUCTION_ACTIVE=TRUE
trap - EXIT
