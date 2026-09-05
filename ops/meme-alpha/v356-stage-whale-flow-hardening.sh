#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v356-stage"
mkdir -p "$STAGE"
cp "$ROOT/ops/meme-alpha/v356-whale-flow-intel.js" "$STAGE/whale-flow-intel-v356.js"
/usr/bin/node --check "$STAGE/whale-flow-intel-v356.js"
TEST=$(/usr/bin/node "$STAGE/whale-flow-intel-v356.js" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'V356_WHALE_FLOW_SELF_TEST=PASS'
echo "$TEST" | grep -q 'HELD_POSITIONS_ALWAYS_MONITORED=TRUE'
echo "$TEST" | grep -q 'NO_CANDIDATES_IS_IDLE_HEALTHY=TRUE'
sha256sum "$STAGE/whale-flow-intel-v356.js" | tee "$STAGE/whale-flow.sha256"
cat > "$STAGE/install-v356.sh" <<'ROOT'
#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V356_INSTALL_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v356-stage"
SRC="$STAGE/whale-flow-intel-v356.js"
DST="$APP/src/whale-flow-intel.js"
OBS="$APP/runtime-status/portfolio-observability.json"
OUT="$APP/runtime-status/whale-flow-intel.json"
SERVICE=meme-alpha-whale-flow.service
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
B="$APP/runtime-status/v356-backup-$STAMP"
mkdir -p "$B"
cp -a "$DST" "$B/whale-flow-intel.js"
[ -f "$OBS" ] && cp -a "$OBS" "$B/portfolio-observability.json" || true
[ -f "$OUT" ] && cp -a "$OUT" "$B/whale-flow-intel.json" || true
rollback(){ rc=$?; if [ $rc -ne 0 ]; then echo V356_ROLLBACK_START=TRUE; cp -a "$B/whale-flow-intel.js" "$DST" || true; [ -f "$B/portfolio-observability.json" ] && cp -a "$B/portfolio-observability.json" "$OBS" || true; [ -f "$B/whale-flow-intel.json" ] && cp -a "$B/whale-flow-intel.json" "$OUT" || true; systemctl restart "$SERVICE" || true; echo V356_ROLLBACK_DONE=TRUE; fi; exit $rc; }
trap rollback EXIT
/usr/bin/node --check "$SRC"
/usr/bin/node "$SRC" --self-test | grep -q 'V356_WHALE_FLOW_SELF_TEST=PASS'
install -o meme-alpha -g meme-alpha -m 0664 /dev/null "$OBS"
install -o root -g root -m 0644 "$SRC" "$DST"
systemctl restart "$SERVICE"
sleep 12
systemctl is-active --quiet "$SERVICE"
/usr/bin/node - "$OUT" "$OBS" <<'NODE'
const fs=require('fs');const w=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const o=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));if(!['HEALTHY','IDLE_HEALTHY'].includes(w.status))throw new Error('WHALE_STATUS_'+w.status);if(o.status==='DEGRADED')throw new Error('OBS_DEGRADED');if(o.stateReadable!==true)throw new Error('STATE_NOT_READABLE_BY_SERVICE');console.log('WHALE_STATUS='+w.status);console.log('WHALE_ROWS='+(w.rows||[]).length);console.log('OBS_OPEN_POSITIONS='+o.openPositions);console.log('OBS_POSITION_MINTS='+JSON.stringify(o.positionMints||[]));
NODE
echo V356_BACKUP="$B"
echo V356_WHALE_FLOW_HARDENING_PRODUCTION_ACTIVE=TRUE
trap - EXIT
ROOT
chmod 0755 "$STAGE/install-v356.sh"
echo ROOT_INSTALL_COMMAND="$STAGE/install-v356.sh"
echo V356_STAGE_READY=TRUE
