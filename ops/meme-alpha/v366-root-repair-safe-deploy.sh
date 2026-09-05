#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V366_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app
WRAP=/usr/local/sbin/meme-alpha-safe-deploy
STATE=/var/lib/meme-alpha/data/micro-live/state.json
ARM=/etc/meme-alpha/micro-live-armed
STAGE="$APP/runtime-status/v366-root-repair"
V360="$APP/runtime-status/v360-stage"
EXPECT='28abda723d5a035d64e8484a7b867772e2fdd35b0920aff1f0bb81267ce0147d'
NAME='micro-live-executor-v360-profit-aware.js'
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACK="$APP/runtime-status/v366-backup-$STAMP"
mkdir -p "$BACK"
cp -a "$WRAP" "$BACK/meme-alpha-safe-deploy"
cp -a "$APP/src/micro-live-executor.js" "$BACK/micro-live-executor.js"
[ -f "$STATE" ] && cp -a "$STATE" "$BACK/state.json" || true
[ -f "$ARM" ] && cp -a "$ARM" "$BACK/micro-live-armed" || true
BEFORE=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync(process.argv[2]));console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()));
NODE
)
rollback(){ rc=$?; if [ "$rc" -ne 0 ]; then echo V366_ROLLBACK_START=TRUE; cp -a "$BACK/meme-alpha-safe-deploy" "$WRAP" || true; cp -a "$BACK/micro-live-executor.js" "$APP/src/micro-live-executor.js" || true; [ -f "$BACK/state.json" ] && cp -a "$BACK/state.json" "$STATE" || true; systemctl restart meme-alpha-micro-live.service || true; echo V366_ROLLBACK_DONE=TRUE; fi; exit "$rc"; }
trap rollback EXIT
cat > "$WRAP" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
BASE=/opt/meme-alpha/app/runtime-status/deploy-candidates
APP=/opt/meme-alpha/app
[ "$#" -eq 3 ] || { echo SAFE_DEPLOY_FAIL=ARGS; exit 2; }
COMP="$1"; NAME="$2"; EXPECT="$3"
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] || { echo SAFE_DEPLOY_FAIL=NAME; exit 2; }
[[ "$EXPECT" =~ ^[a-f0-9]{64}$ ]] || { echo SAFE_DEPLOY_FAIL=SHA; exit 2; }
SRC="$BASE/$NAME"
[ -f "$SRC" ] && [ ! -L "$SRC" ] || { echo SAFE_DEPLOY_FAIL=SOURCE; exit 2; }
REAL=$(readlink -f "$SRC"); [[ "$REAL" == "$BASE/"* ]] || { echo SAFE_DEPLOY_FAIL=PATH; exit 2; }
ACT=$(sha256sum "$SRC" | awk '{print $1}'); [ "$ACT" = "$EXPECT" ] || { echo SAFE_DEPLOY_FAIL=HASH_MISMATCH; exit 2; }
case "$COMP" in
  executor) DST="$APP/src/micro-live-executor.js"; SERVICE=meme-alpha-micro-live.service ;;
  whale) DST="$APP/src/whale-flow-intel.js"; SERVICE=meme-alpha-whale-flow.service ;;
  realtime) DST="$APP/src/realtime-pool-pulse.js"; SERVICE=meme-alpha-realtime-pulse.service ;;
  radar) DST="$APP/src/new-listing-radar.js"; SERVICE=meme-alpha-paper.service ;;
  trend) DST="$APP/src/trend-pulse.js"; SERVICE=meme-alpha-trend-pulse.service ;;
  scanner) DST="$APP/src/scanner.js"; SERVICE=meme-alpha-paper.service ;;
  signal) DST="$APP/src/safe-signal-export.js"; SERVICE=meme-alpha-paper.service ;;
  gate) DST="$APP/src/micro-live-gate.js"; SERVICE=meme-alpha-paper.service ;;
  *) echo SAFE_DEPLOY_FAIL=COMPONENT; exit 2 ;;
esac
runuser -u github-runner -- /usr/bin/node --check "$SRC"
STAMP=$(date -u +%Y%m%dT%H%M%SZ); B="$APP/runtime-status/safe-deploy-backup-$STAMP-$COMP"; mkdir -p "$B"; cp -a "$DST" "$B/old.js"
rollback(){ rc=$?; if [ "$rc" -ne 0 ]; then cp -a "$B/old.js" "$DST" || true; systemctl restart "$SERVICE" || true; echo SAFE_DEPLOY_ROLLBACK=TRUE; fi; exit "$rc"; }
trap rollback EXIT
if [ "$COMP" = executor ]; then
  # The executor service itself is the transaction-capable process. Stopping it is the
  # deployment disarm. /etc is intentionally mounted read-only, so never mutate arming.
  systemctl stop "$SERVICE"
  ! systemctl is-active --quiet "$SERVICE" || { echo SAFE_DEPLOY_FAIL=EXECUTOR_DID_NOT_STOP; exit 3; }
  [ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 0 ] || { echo SAFE_DEPLOY_FAIL=EXECUTOR_PROCESS_STILL_RUNNING; exit 3; }
fi
install -o root -g root -m 0644 "$SRC" "$DST"
systemctl restart "$SERVICE"; sleep 4; systemctl is-active --quiet "$SERVICE"
if [ "$COMP" = executor ]; then [ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]; fi
echo SAFE_DEPLOY_COMPONENT="$COMP"; echo SAFE_DEPLOY_SHA="$ACT"; echo SAFE_DEPLOY_BACKUP="$B"; echo SAFE_DEPLOY_DISARM=SERVICE_STOP_NO_ARM_FILE_WRITE; echo SAFE_DEPLOY_SUCCESS=TRUE
trap - EXIT
WRAPPER
chown root:root "$WRAP"; chmod 0755 "$WRAP"; bash -n "$WRAP"
# Existing sudoers authorization is intentionally left unchanged.
grep -q 'SAFE_DEPLOY_DISARM=SERVICE_STOP_NO_ARM_FILE_WRITE' "$WRAP"
# Validate the exact already-staged executor before production activation.
[ -f "$APP/runtime-status/deploy-candidates/$NAME" ] || { echo V366_FAIL=V360_CANDIDATE_MISSING; exit 4; }
ACT=$(sha256sum "$APP/runtime-status/deploy-candidates/$NAME" | awk '{print $1}')
[ "$ACT" = "$EXPECT" ] || { echo V366_FAIL=V360_HASH_MISMATCH; exit 4; }
/usr/bin/node --check "$APP/runtime-status/deploy-candidates/$NAME"
/usr/bin/node "$APP/runtime-status/deploy-candidates/$NAME" --self-test | grep -q 'MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS'
"$WRAP" executor "$NAME" "$EXPECT"
sleep 3
PROD=$(sha256sum "$APP/src/micro-live-executor.js" | awk '{print $1}')
[ "$PROD" = "$EXPECT" ]
systemctl is-active --quiet meme-alpha-micro-live.service
[ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]
AFTER=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync(process.argv[2]));if(s.version!=='3.60.0-profit-aware-exits')throw new Error('STATE_VERSION');console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()));
NODE
)
[ "$BEFORE" = "$AFTER" ] || { echo V366_POSITION_PRESERVATION_FAIL; exit 5; }
echo V366_BACKUP="$BACK"
echo PRESERVED_MINTS="$AFTER"
echo V366_SAFE_DEPLOY_WRAPPER_REPAIRED=TRUE
echo V360_PROFIT_AWARE_PRODUCTION_ACTIVE=TRUE
trap - EXIT
