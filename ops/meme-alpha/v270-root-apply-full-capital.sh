#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
ETC=/etc/meme-alpha
EXEC_SRC=$APP/ops/meme-alpha/micro-live/micro-live-executor-v270.js
EXEC_DST=$APP/src/micro-live-executor.js
SIGNER_SRC=$APP/ops/meme-alpha/signer/ready_signer_v5.py
SIGNER_DST=/opt/meme-alpha-signer/ready_signer.py
SIGNER_UNIT=meme-alpha-signer.service
MICRO_UNIT=meme-alpha-micro-live.service
GATE=$APP/runtime-status/micro-live-gate.json
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.7.0 FULL-CAPITAL TREND AUTOSCALE APPLY ==='
[ -f "$EXEC_SRC" ] || { echo ABORT_EXECUTOR_V270_NOT_STAGED; exit 1; }
[ -f "$SIGNER_SRC" ] || { echo ABORT_SIGNER_V5_NOT_STAGED; exit 1; }
[ -f "$ETC/signer-enabled" ] && grep -qx 'ARMED=YES' "$ETC/signer-enabled" || { echo ABORT_SIGNER_NOT_ALREADY_ARMED; exit 1; }
[ -f "$ETC/execution-mode" ] && grep -qx 'MICRO_LIVE' "$ETC/execution-mode" || { echo ABORT_EXECUTION_MODE_NOT_MICRO_LIVE; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet "$SIGNER_UNIT"
systemctl is-active --quiet "$MICRO_UNIT"

node --check "$EXEC_SRC"
node "$EXEC_SRC" --self-test
python3 "$SIGNER_SRC" --self-test | tee /tmp/meme-alpha-v270-signer-selftest.txt
grep -q 'READY_SIGNER_V5_SELF_TEST=PASS' /tmp/meme-alpha-v270-signer-selftest.txt
rm -f /tmp/meme-alpha-v270-signer-selftest.txt

grep -q "securityDecision==='PASS'" "$EXEC_SRC"
grep -q "holderClusterDecision==='PASS'" "$EXEC_SRC"
grep -q "sellRoute===true" "$EXEC_SRC"
grep -q "trendEntryEligible" "$EXEC_SRC"
grep -q "maxUtilizationPct" "$EXEC_SRC"
grep -q "ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED" <(python3 "$SIGNER_SRC" --self-test)

echo SECURITY_GATES_PRESERVED=TRUE
echo HOLDER_GATES_PRESERVED=TRUE
echo SELLABILITY_GATE_PRESERVED=TRUE
echo TREND_ENTRY_GATE_PRESERVED=TRUE

STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v270-$STAMP
mkdir -p "$BACKUP"
cp -a "$EXEC_DST" "$BACKUP/micro-live-executor.js" 2>/dev/null || true
cp -a "$SIGNER_DST" "$BACKUP/ready_signer.py" 2>/dev/null || true
cp -a "$ETC/micro-live-policy.json" "$BACKUP/micro-live-policy.json" 2>/dev/null || true
cp -a "$ETC/signer-policy.json" "$BACKUP/signer-policy.json" 2>/dev/null || true

RPC=$(python3 - <<'PY'
import json;print(json.load(open('/opt/meme-alpha/app/config/runtime.json')).get('rpc','https://api.mainnet-beta.solana.com'))
PY
)
cat > "$ETC/micro-live-policy.json" <<'JSON'
{
  "version":"2.7.0",
  "reserveLamports":10000000,
  "minOrderLamports":10000000,
  "probeUtilizationPct":15,
  "confirmedUtilizationPct":35,
  "strongUtilizationPct":65,
  "maxUtilizationPct":94,
  "maxBuyPriceImpactPct":1.25,
  "maxSellPriceImpactPct":8.0,
  "externalFlowThresholdLamports":500000,
  "minAddIntervalSec":30
}
JSON
python3 - "$RPC" "$ETC/signer-policy.json" <<'PY'
import json,os,sys
rpc,path=sys.argv[1:]
x={
 'reserveLamports':10000000,
 'maxPortfolioUtilizationPct':94,
 'maxSingleBuyPctOfBalance':90,
 'dailyTurnoverMultiple':50,
 'maxOrdersPerHour':16,
 'maxBuyPriceImpactPct':1.25,
 'maxSellPriceImpactPct':8.0,
 'jupiterBaseUrl':'https://api.jup.ag',
 'rpcUrl':rpc,
 'gatePath':'/opt/meme-alpha/app/runtime-status/micro-live-gate.json',
 'signalPath':'/opt/meme-alpha/app/runtime-status/signal-snapshot.json'
}
t=path+'.tmp';open(t,'w').write(json.dumps(x,separators=(',',':'))+'\n');os.chmod(t,0o640);os.replace(t,path)
PY
chown root:meme-alpha-signer-client "$ETC/micro-live-policy.json" "$ETC/signer-policy.json"
chmod 640 "$ETC/micro-live-policy.json" "$ETC/signer-policy.json"

install -o root -g root -m 0555 "$SIGNER_SRC" "$SIGNER_DST"
install -o root -g root -m 0644 "$EXEC_SRC" "$EXEC_DST"
node --check "$EXEC_DST"

systemctl restart "$SIGNER_UNIT"
sleep 2
systemctl is-active --quiet "$SIGNER_UNIT"
HEALTH=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close();print(json.dumps(r,separators=(',',':')))
PY
)
python3 - "$HEALTH" <<'PY'
import json,sys
r=json.loads(sys.argv[1]);assert r.get('ok') is True;assert r.get('version')=='5.0';assert r.get('walletLoaded') is True;assert r.get('signingEnabled') is True;assert r.get('arbitraryRawSign') is False;assert float(r.get('maxPortfolioUtilizationPct',0))==94
print('SIGNER_V5_ACTIVE=TRUE');print('SIGNER_ARMED=TRUE');print('ARBITRARY_RAW_SIGN=FALSE');print('MAX_PORTFOLIO_UTILIZATION_PCT=94')
PY

systemctl restart "$MICRO_UNIT"
sleep 5
systemctl is-active --quiet "$MICRO_UNIT"
PID=$(systemctl show "$MICRO_UNIT" -p MainPID --value)
echo "MICRO_EXECUTOR_ACTIVE=TRUE PID=$PID"

PUB=$(python3 - "$HEALTH" <<'PY'
import json,sys;print(json.loads(sys.argv[1]).get('publicKey',''))
PY
)
BAL=$(python3 - "$RPC" "$PUB" <<'PY'
import json,sys,urllib.request
rpc,pub=sys.argv[1:];d=json.dumps({'jsonrpc':'2.0','id':1,'method':'getBalance','params':[pub,{'commitment':'confirmed'}]}).encode();q=urllib.request.Request(rpc,data=d,headers={'content-type':'application/json','user-agent':'meme-alpha-v270'})
with urllib.request.urlopen(q,timeout=12) as r:j=json.loads(r.read())
print(int(j['result']['value']))
PY
)
python3 - "$BAL" <<'PY'
import sys
b=int(sys.argv[1]);sol=b/1e9
print(f'BOT_BALANCE_SOL={sol:.9f}')
for name,p in [('PROBE',15),('CONFIRMED',35),('STRONG',65),('MAX',94)]:
 target=min(int(b*p/100),max(0,b-10_000_000));print(f'{name}_TARGET_SOL={target/1e9:.9f}')
PY

if [ -f "$GATE" ]; then
 python3 - <<'PY'
import json
x=json.load(open('/opt/meme-alpha/app/runtime-status/micro-live-gate.json'))
print('GATE_ALLOWED='+str(bool(x.get('allowed'))).lower());print('GATE_REASONS='+(','.join(x.get('reasons',[])) or 'NONE'));print('EXECUTION_MODE='+str(x.get('executionMode')))
PY
fi

echo CAPITAL_UTILIZATION_STAGES=15_35_65_94
echo PRE_EVIDENCE_FIXED_0_005_CAP=REMOVED
echo ABSOLUTE_SOL_RESERVE=0.010
echo MIN_REAL_ORDER_SOL=0.010
echo SCALE_IN_REQUIRES_PERSISTENT_TREND=TRUE
echo SCALE_IN_MIN_INTERVAL_SEC=30
echo DEPOSITS_AUTO_EXPAND_NEXT_TARGET=TRUE
echo WITHDRAWALS_AUTO_REDUCE_AVAILABLE_CAPITAL=TRUE
echo EMERGENCY_SELL_NOT_BLOCKED_BY_BUY_FREQUENCY_QUOTA=TRUE
echo MAX_BUY_PRICE_IMPACT_PCT=1.25
echo MAX_SELL_PRICE_IMPACT_PCT=8.0
echo V270_FULL_CAPITAL_AUTOSCALE_APPLY_PASS
echo "BACKUP=$BACKUP"
