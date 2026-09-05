#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v351-stage"
OUT="$STAGE/micro-live-executor-v351-adaptive-alpha.js"
RADAR="$STAGE/new-listing-radar-v351.js"
mkdir -p "$STAGE"
cp "$APP/src/micro-live-executor.js" "$OUT"
cp "$APP/src/new-listing-radar.js" "$RADAR"
cp "$ROOT/ops/meme-alpha/v350-realtime-pool-pulse.js" "$STAGE/realtime-pool-pulse.js"
cp "$ROOT/ops/meme-alpha/v350-whale-flow-intel.js" "$STAGE/whale-flow-intel.js"
python3 "$ROOT/ops/meme-alpha/v351-patch-executor.py" "$OUT"
python3 - "$RADAR" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
if 'const MAX_MINTS=60;' in s:s=s.replace('const MAX_MINTS=60;','const MAX_MINTS=90;',1)
elif 'const MAX_MINTS=90;' not in s:raise SystemExit('RADAR_MAX_MINTS_UNKNOWN')
s=s.replace("version:'3.18.0'","version:'3.51.0'",1)
p.write_text(s)
PY
/usr/bin/node --check "$OUT"
/usr/bin/node --check "$RADAR"
/usr/bin/node --check "$STAGE/realtime-pool-pulse.js"
/usr/bin/node --check "$STAGE/whale-flow-intel.js"
TEST=$(/usr/bin/node "$OUT" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'MICRO_EXECUTOR_V351_ADAPTIVE_ALPHA_SELF_TEST=PASS'
echo "$TEST" | grep -q 'REALTIME_POOL_PULSE_INTEGRATION=TRUE'
echo "$TEST" | grep -q 'ONCHAIN_WHALE_FLOW_INTEGRATION=TRUE'
echo "$TEST" | grep -q 'ONLINE_EXPECTANCY_LEARNING=TRUE'
echo "$TEST" | grep -q 'JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE'
/usr/bin/node "$STAGE/realtime-pool-pulse.js" --self-test | grep -q 'V350_REALTIME_POOL_PULSE_SELF_TEST=PASS'
/usr/bin/node "$STAGE/whale-flow-intel.js" --self-test | grep -q 'V350_WHALE_FLOW_SELF_TEST=PASS'
sha256sum "$OUT" | tee "$STAGE/executor.sha256"
cat > "$STAGE/install-v351.sh" <<'ROOT'
#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V351_INSTALL_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app; STAGE="$APP/runtime-status/v351-stage"; DST="$APP/src/micro-live-executor.js"; RADAR="$APP/src/new-listing-radar.js"; RUN="$APP/run-paper.sh"; STATE=/var/lib/meme-alpha/data/micro-live/state.json; ARM=/etc/meme-alpha/micro-live-armed; SERVICE=meme-alpha-micro-live.service
STAMP=$(date -u +%Y%m%dT%H%M%SZ); B="$APP/runtime-status/v351-backup-$STAMP"; mkdir -p "$B"
cp -a "$DST" "$B/micro-live-executor.js"; cp -a "$RADAR" "$B/new-listing-radar.js"; cp -a "$RUN" "$B/run-paper.sh"; [ -f "$STATE" ] && cp -a "$STATE" "$B/state.json" || true; cp -a "$ARM" "$B/micro-live-armed"
for f in /etc/systemd/system/meme-alpha-realtime-pulse.service /etc/systemd/system/meme-alpha-whale-flow.service; do [ -f "$f" ] && cp -a "$f" "$B/$(basename "$f")" || true; done
BEFORE=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()))
NODE
)
rollback(){ rc=$?; if [ $rc -ne 0 ]; then echo V351_ROLLBACK_START=TRUE; printf 'ARMED=NO\n' > "$ARM" || true; systemctl stop "$SERVICE" meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service 2>/dev/null || true; cp -a "$B/micro-live-executor.js" "$DST" || true; cp -a "$B/new-listing-radar.js" "$RADAR" || true; cp -a "$B/run-paper.sh" "$RUN" || true; [ -f "$B/state.json" ] && cp -a "$B/state.json" "$STATE" || true; cp -a "$B/micro-live-armed" "$ARM" || true; for f in meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service; do [ -f "$B/$f" ] && cp -a "$B/$f" "/etc/systemd/system/$f" || rm -f "/etc/systemd/system/$f"; done; systemctl daemon-reload || true; systemctl restart meme-alpha-paper.service "$SERVICE" || true; echo V351_ROLLBACK_DONE=TRUE; fi; exit $rc; }
trap rollback EXIT
/usr/bin/node --check "$STAGE/micro-live-executor-v351-adaptive-alpha.js"; /usr/bin/node "$STAGE/micro-live-executor-v351-adaptive-alpha.js" --self-test | grep -q 'MICRO_EXECUTOR_V351_ADAPTIVE_ALPHA_SELF_TEST=PASS'
printf 'ARMED=NO\n' > "$ARM"; systemctl stop "$SERVICE"
install -o root -g root -m 0644 "$STAGE/micro-live-executor-v351-adaptive-alpha.js" "$DST"
install -o root -g root -m 0644 "$STAGE/new-listing-radar-v351.js" "$RADAR"
install -o root -g root -m 0644 "$STAGE/realtime-pool-pulse.js" "$APP/src/realtime-pool-pulse.js"
install -o root -g root -m 0644 "$STAGE/whale-flow-intel.js" "$APP/src/whale-flow-intel.js"
python3 - "$RUN" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text();s=re.sub(r'^LIVE_SIGNAL_MAX_AGE_SEC=\d+$','LIVE_SIGNAL_MAX_AGE_SEC=60',s,count=1,flags=re.M);s=s.replace('/usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1\n      sleep 5','/usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1\n      sleep 1',1);p.write_text(s)
PY
grep -q '^LIVE_SIGNAL_MAX_AGE_SEC=60$' "$RUN"; grep -q 'paperExecutionEnabled:false' "$RUN"; ! grep -q '/usr/bin/node src/position.js' "$RUN"
install -o meme-alpha -g meme-alpha -m 0664 /dev/null "$APP/runtime-status/realtime-pool-pulse.json"; install -o meme-alpha -g meme-alpha -m 0664 /dev/null "$APP/runtime-status/whale-flow-intel.json"
cat > /etc/systemd/system/meme-alpha-realtime-pulse.service <<'UNIT'
[Unit]
Description=Meme Alpha realtime pool pulse
After=network-online.target meme-alpha-paper.service
Wants=network-online.target
[Service]
Type=simple
User=meme-alpha
Group=meme-alpha
ExecStart=/usr/bin/node /opt/meme-alpha/app/src/realtime-pool-pulse.js
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/meme-alpha-whale-flow.service <<'UNIT'
[Unit]
Description=Meme Alpha on-chain whale flow intelligence
After=network-online.target meme-alpha-paper.service
Wants=network-online.target
[Service]
Type=simple
User=meme-alpha
Group=meme-alpha
ExecStart=/usr/bin/node /opt/meme-alpha/app/src/whale-flow-intel.js
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload; systemctl enable --now meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service; systemctl restart meme-alpha-paper.service; systemctl start "$SERVICE"; sleep 10
systemctl is-active --quiet "$SERVICE"; systemctl is-active --quiet meme-alpha-paper.service; systemctl is-active --quiet meme-alpha-realtime-pulse.service; systemctl is-active --quiet meme-alpha-whale-flow.service
[ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]
AFTER=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));if(s.version!=='3.51.0-adaptive-alpha')throw new Error('STATE_VERSION');console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()))
NODE
)
[ "$BEFORE" = "$AFTER" ] || { echo V351_POSITION_PRESERVATION_FAIL; exit 1; }
cp -a "$B/micro-live-armed" "$ARM"; systemctl restart "$SERVICE"; sleep 4; systemctl is-active --quiet "$SERVICE"
echo V351_BACKUP="$B"; echo PRESERVED_MINTS="$AFTER"; echo V351_ADAPTIVE_ALPHA_PRODUCTION_ACTIVE=TRUE
trap - EXIT
ROOT
chmod 0755 "$STAGE/install-v351.sh"
echo ROOT_INSTALL_COMMAND="$STAGE/install-v351.sh"
echo V351_STAGE_READY=TRUE
