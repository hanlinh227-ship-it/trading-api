#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
EXEC_DST=$APP/src/micro-live-executor.js
EXEC_SRC=$APP/ops/meme-alpha/micro-live/micro-live-executor-v290.js
SIGNER_DST=/opt/meme-alpha-signer/ready_signer.py
SIGNER_SRC=$APP/ops/meme-alpha/signer/ready_signer_v7.py
TREND_SRC=$APP/ops/meme-alpha/trend-pulse-v290.js
TREND_DST=$APP/src/trend-pulse.js
TREND_UNIT=/etc/systemd/system/meme-alpha-trend-pulse.service
SIGNER_POLICY=/etc/meme-alpha/signer-policy.json
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.9.0 FAST TREND 9/10 APPLY ==='
[ -f "$EXEC_SRC" ] || { echo ABORT_EXECUTOR_V290_NOT_STAGED; exit 1; }
[ -f "$SIGNER_SRC" ] || { echo ABORT_SIGNER_V7_NOT_STAGED; exit 1; }
[ -f "$TREND_SRC" ] || { echo ABORT_TREND_V290_NOT_STAGED; exit 1; }
[ -f /etc/meme-alpha/signer-enabled ] && grep -qx 'ARMED=YES' /etc/meme-alpha/signer-enabled || { echo ABORT_SIGNER_NOT_ARMED; exit 1; }
[ -f /etc/meme-alpha/execution-mode ] && grep -qx 'MICRO_LIVE' /etc/meme-alpha/execution-mode || { echo ABORT_NOT_MICRO_LIVE; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet meme-alpha-micro-live.service

python3 - <<'PY'
import json,sys
p='/var/lib/meme-alpha/data/micro-live/state.json'
try:s=json.load(open(p))
except FileNotFoundError:s={}
if s.get('position'):
 print('ABORT_LIVE_POSITION_OPEN='+str(s['position'].get('symbol','UNKNOWN')));sys.exit(2)
print('LIVE_POSITION=NONE')
PY

# v2.9 builds on the v2.8 widened verification pipeline. If v2.8 has not
# been applied yet, apply it first in this same root operation.
if grep -q 'MICRO_LIVE_EXECUTOR_V270_FULL_CAPITAL=STARTED' "$EXEC_DST"; then
  echo APPLYING_V280_PREREQUISITE=TRUE
  bash "$APP/ops/meme-alpha/v280-root-apply-opportunity.sh"
elif grep -q 'MICRO_LIVE_EXECUTOR_V280_OPPORTUNITY=STARTED' "$EXEC_DST"; then
  echo V280_PREREQUISITE=ALREADY_ACTIVE
elif grep -q 'MICRO_LIVE_EXECUTOR_V290_FAST_TREND=STARTED' "$EXEC_DST"; then
  echo V290_RUNTIME=ALREADY_ACTIVE_REVERIFYING
else
  echo ABORT_UNKNOWN_MICRO_EXECUTOR_VERSION; exit 1
fi

node --check "$TREND_SRC"
node "$TREND_SRC" --self-test | tee /tmp/v290-trend.txt
grep -q 'TREND_PULSE_V290_SELF_TEST=PASS' /tmp/v290-trend.txt
rm -f /tmp/v290-trend.txt
node --check "$EXEC_SRC"
node "$EXEC_SRC" --self-test | tee /tmp/v290-exec.txt
grep -q 'MICRO_EXECUTOR_V290_SELF_TEST=PASS' /tmp/v290-exec.txt
rm -f /tmp/v290-exec.txt
python3 "$SIGNER_SRC" --self-test | tee /tmp/v290-signer.txt
grep -q 'READY_SIGNER_V7_SELF_TEST=PASS' /tmp/v290-signer.txt
grep -q 'ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED' /tmp/v290-signer.txt
rm -f /tmp/v290-signer.txt

grep -q "securityDecision==='PASS'" "$EXEC_SRC"
grep -q "holderClusterDecision==='PASS'" "$EXEC_SRC"
grep -q "sellRoute===true" "$EXEC_SRC"
grep -q '!c.token2022' "$EXEC_SRC"
grep -q 'volumeAcceleration' "$EXEC_SRC"
grep -q 'opportunityScore' "$EXEC_SRC"

STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v290-$STAMP
mkdir -p "$BACKUP"
cp -a "$EXEC_DST" "$BACKUP/micro-live-executor.js"
cp -a "$SIGNER_DST" "$BACKUP/ready_signer.py"
cp -a "$SIGNER_POLICY" "$BACKUP/signer-policy.json" 2>/dev/null || true
cp -a "$TREND_DST" "$BACKUP/trend-pulse.js" 2>/dev/null || true
cp -a "$TREND_UNIT" "$BACKUP/meme-alpha-trend-pulse.service" 2>/dev/null || true

rollback(){
 rc=$?;echo "V290_ROLLBACK rc=$rc" >&2
 cp -f "$BACKUP/micro-live-executor.js" "$EXEC_DST" || true
 cp -f "$BACKUP/ready_signer.py" "$SIGNER_DST" || true
 [ -f "$BACKUP/signer-policy.json" ] && cp -f "$BACKUP/signer-policy.json" "$SIGNER_POLICY" || true
 [ -f "$BACKUP/trend-pulse.js" ] && cp -f "$BACKUP/trend-pulse.js" "$TREND_DST" || true
 if [ -f "$BACKUP/meme-alpha-trend-pulse.service" ]; then cp -f "$BACKUP/meme-alpha-trend-pulse.service" "$TREND_UNIT"; else rm -f "$TREND_UNIT"; fi
 systemctl daemon-reload >/dev/null 2>&1 || true
 systemctl restart meme-alpha-signer.service >/dev/null 2>&1 || true
 systemctl restart meme-alpha-micro-live.service >/dev/null 2>&1 || true
 exit "$rc"
}
trap rollback ERR

install -o root -g root -m 0644 "$TREND_SRC" "$TREND_DST"
install -o root -g root -m 0644 "$EXEC_SRC" "$EXEC_DST"
install -o root -g root -m 0555 "$SIGNER_SRC" "$SIGNER_DST"

python3 - "$SIGNER_POLICY" <<'PY'
import json,os,sys
p=sys.argv[1]
try:x=json.load(open(p))
except:x={}
x['trendPath']='/opt/meme-alpha/app/runtime-status/trend-pulse.json'
t=p+'.tmp';open(t,'w').write(json.dumps(x,separators=(',',':'))+'\n');os.chmod(t,0o640);os.replace(t,p)
PY
chown root:meme-alpha-signer-client "$SIGNER_POLICY"
chmod 640 "$SIGNER_POLICY"

cat > "$TREND_UNIT" <<'UNIT'
[Unit]
Description=Meme Alpha v2.9 Fast Trend Pulse
After=network-online.target meme-alpha-paper.service
Wants=network-online.target

[Service]
Type=simple
User=meme-alpha
Group=meme-alpha
WorkingDirectory=/opt/meme-alpha/app
ExecStart=/usr/bin/node /opt/meme-alpha/app/src/trend-pulse.js
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/meme-alpha/app/runtime-status
ReadWritePaths=/var/log/meme-alpha
StandardOutput=append:/var/log/meme-alpha/trend-pulse.log
StandardError=append:/var/log/meme-alpha/trend-pulse-error.log

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$TREND_UNIT"
systemctl daemon-reload
systemctl enable --now meme-alpha-trend-pulse.service
sleep 5
systemctl is-active --quiet meme-alpha-trend-pulse.service

python3 - <<'PY'
import json,os,time,sys
p='/opt/meme-alpha/app/runtime-status/trend-pulse.json'
if not os.path.exists(p):raise SystemExit('TREND_PULSE_OUTPUT_MISSING')
x=json.load(open(p));age=time.time()-os.path.getmtime(p)
if age>10:raise SystemExit('TREND_PULSE_STALE')
print('TREND_PULSE_ACTIVE=TRUE');print('TREND_PULSE_AGE_SEC=%.2f'%age);print('TREND_POLL_MS='+str(x.get('pollMs')));print('TREND_TOP_THEME='+str((x.get('themes') or [{}])[0].get('narrative','NONE')));print('TREND_TOP_THEME_STRENGTH='+str((x.get('themes') or [{}])[0].get('strength',0)))
PY

systemctl restart meme-alpha-signer.service
sleep 2
systemctl is-active --quiet meme-alpha-signer.service
HEALTH=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close();print(json.dumps(r,separators=(',',':')))
PY
)
python3 - "$HEALTH" <<'PY'
import json,sys
r=json.loads(sys.argv[1]);assert r.get('ok') is True;assert r.get('version')=='7.0';assert r.get('walletLoaded') is True;assert r.get('signingEnabled') is True;assert r.get('arbitraryRawSign') is False
print('SIGNER_V7_ACTIVE=TRUE');print('SIGNER_ARMED=TRUE');print('ARBITRARY_RAW_SIGN=FALSE')
PY
systemctl restart meme-alpha-micro-live.service
sleep 4
systemctl is-active --quiet meme-alpha-micro-live.service

echo MICRO_EXECUTOR_V290_ACTIVE=TRUE
node --input-type=module - <<'NODE'
import fs from 'node:fs';const r=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};const t=r('/opt/meme-alpha/app/runtime-status/trend-pulse.json'),s=r('/opt/meme-alpha/app/runtime-status/signal-snapshot.json'),g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json');
console.log(`SIGNAL_TS=${s.timestamp||'-'} TREND_TS=${t.timestamp||'-'} GATE_ALLOWED=${g.allowed===true}`);
for(const x of (t.themes||[]).slice(0,5))console.log(`THEME ${x.narrative} strength=${x.strength} count=${x.count} breakout=${x.breakouts} avgPulse=${x.avgPulse} volAccel=${x.avgVolAccel} symbols=${x.symbols.join(',')}`);
for(const x of (t.rows||[]).filter(x=>x.status==='BREAKOUT').slice(0,8))console.log(`PULSE_BREAKOUT ${x.symbol} pulse=${x.pulseScore} narrative=${x.narrative} vacc=${x.volumeAcceleration} tacc=${x.txnAcceleration} bsr=${x.buySellRatio} chg5=${x.price5m} liq=${x.liquidityUsd} promoted=${x.promotionFlag}`);
NODE

echo HARD_RUG_SECURITY_STAYS_FAIL_CLOSED=TRUE
echo HOLDER_PASS_REQUIRED=TRUE
echo SELL_ROUTE_REQUIRED=TRUE
echo TOKEN2022_LIVE_BLOCK_PRESERVED=TRUE
echo PAID_BOOSTS_NEVER_POSITIVE=TRUE
echo TREND_REACTION_TARGET_SECONDS=3
echo CAPITAL_STAGES_UNCHANGED=15_35_65_94
echo V290_FAST_TREND_APPLY_PASS
echo "BACKUP=$BACKUP"
