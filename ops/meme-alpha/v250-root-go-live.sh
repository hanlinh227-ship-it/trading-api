#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
ETC=/etc/meme-alpha
KEYDIR=/var/lib/meme-alpha-signer/keys
KEY=$KEYDIR/bot-keypair.json
POLICY=$ETC/micro-live-policy.json
SIGNER_POLICY=$ETC/signer-policy.json
SIGNER_SRC=$APP/ops/meme-alpha/signer/ready_signer_v4.py
SIGNER_DST=/opt/meme-alpha-signer/ready_signer.py
SIGNER_UNIT=meme-alpha-signer.service
MICRO_UNIT=meme-alpha-micro-live.service
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
GATE=$APP/runtime-status/micro-live-gate.json

[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.5.1 ADAPTIVE COMPOUND MICRO-LIVE ACTIVATION ==='

python3 - <<'PY'
import json
c=json.load(open('/opt/meme-alpha/app/config/runtime.json'))
assert c.get('mode')=='PAPER','ABORT_ANALYSIS_ENGINE_NOT_PAPER'
print('ANALYSIS_ENGINE=PAPER_CONTINUOUS')
PY
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_NOT_ISOLATED; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service || { echo ABORT_SIGNAL_ENGINE_INACTIVE; exit 1; }
systemctl is-active --quiet "$SIGNER_UNIT" || { echo ABORT_SIGNER_INACTIVE; exit 1; }
[ -f /etc/systemd/system/$MICRO_UNIT ] || { echo ABORT_MICRO_EXECUTOR_NOT_INSTALLED; exit 1; }
grep -q 'MICRO_LIVE_EXECUTOR_V250' "$APP/src/micro-live-executor.js" || { echo ABORT_V250_EXECUTOR_NOT_INSTALLED; exit 1; }
grep -q "version:'2.4.0'" "$APP/src/micro-live-gate.js" || { echo ABORT_V240_GATE_NOT_INSTALLED; exit 1; }
[ -f "$SIGNER_SRC" ] || { echo ABORT_SIGNER_V4_NOT_STAGED; exit 1; }
python3 "$SIGNER_SRC" --self-test | grep -q 'READY_SIGNER_V4_SELF_TEST=PASS'
if sudo -u github-runner test -r "$KEYDIR" || sudo -u github-runner test -x "$KEYDIR"; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if sudo -u github-runner test -r /run/meme-alpha-signer/signer.sock || sudo -u github-runner test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi
echo RUNNER_ISOLATION=PASS

# Begin locked. The runner cannot arm signing or create/read the wallet.
rm -f "$ETC/signer-enabled" "$ETC/micro-live-armed" "$ETC/execution-mode"
systemctl disable --now "$MICRO_UNIT" >/dev/null 2>&1 || true
install -d -o root -g meme-alpha-signer-client -m 0750 "$ETC"
install -d -o meme-alpha-signer -g meme-alpha-signer -m 0700 "$KEYDIR"

# Install signer v4 under root ownership. It independently re-checks the live gate,
# eligible signal mint, wallet balance, utilization and reserve before every BUY.
install -o root -g root -m 0555 "$SIGNER_SRC" "$SIGNER_DST"
RPC=$(python3 - <<'PY'
import json;print(json.load(open('/opt/meme-alpha/app/config/runtime.json')).get('rpc','https://api.mainnet-beta.solana.com'))
PY
)
python3 - "$RPC" "$SIGNER_POLICY" <<'PY'
import json,os,sys
rpc,path=sys.argv[1:]
x={
 'microMaxBuyLamports':5000000,
 'microReserveLamports':20000000,
 'scaledReserveLamports':10000000,
 'maxUtilizationPct':90,
 'dailyTurnoverMultiple':50,
 'maxOrdersPerHour':12,
 'maxPriceImpactPct':1.25,
 'jupiterBaseUrl':'https://api.jup.ag',
 'rpcUrl':rpc,
 'gatePath':'/opt/meme-alpha/app/runtime-status/micro-live-gate.json',
 'signalPath':'/opt/meme-alpha/app/runtime-status/signal-snapshot.json'
}
t=path+'.tmp';open(t,'w').write(json.dumps(x,separators=(',',':'))+'\n');os.chmod(t,0o640);os.replace(t,path)
PY
chown root:meme-alpha-signer-client "$SIGNER_POLICY";chmod 640 "$SIGNER_POLICY"

# Executor capital policy: tiny real-money discovery first, adaptive compounding only
# after scaleAllowed=true from validation/stress evidence.
cat > "$POLICY" <<'JSON'
{
  "version":"2.5.1",
  "microMaxEntryLamports":5000000,
  "microReserveLamports":20000000,
  "scaledReserveLamports":10000000,
  "baseUtilizationPct":70,
  "strongUtilizationPct":82,
  "maxUtilizationPct":90,
  "maxPriceImpactPct":1.25,
  "externalFlowThresholdLamports":500000,
  "initialFundingMinLamports":30000000,
  "initialFundingMaxLamports":100000000
}
JSON
chown root:meme-alpha-signer-client "$POLICY";chmod 640 "$POLICY"

if [ ! -f "$KEY" ]; then
python3 - <<'PY'
import json,os,subprocess
key='/var/lib/meme-alpha-signer/keys/bot-keypair.json';seed=os.urandom(32);der=bytes.fromhex('302e020100300506032b657004220420')+seed
p=subprocess.run(['openssl','pkey','-inform','DER','-pubout','-outform','DER'],input=der,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=5);pub=p.stdout[-32:]
if len(pub)!=32: raise SystemExit('PUBKEY_DER_FAIL')
t=key+'.tmp';open(t,'w').write(json.dumps(list(seed+pub),separators=(',',':'))+'\n');os.chmod(t,0o600);os.replace(t,key)
PY
chown meme-alpha-signer:meme-alpha-signer "$KEY";chmod 600 "$KEY";echo WALLET_CREATED=TRUE
else
[ "$(stat -c %U:%G "$KEY")" = meme-alpha-signer:meme-alpha-signer ] || { echo ABORT_WALLET_OWNER; exit 1; }
[ "$(stat -c %a "$KEY")" = 600 ] || { echo ABORT_WALLET_MODE; exit 1; }
echo WALLET_CREATED=ALREADY_EXISTS
fi

systemctl restart "$SIGNER_UNIT";sleep 1;systemctl is-active --quiet "$SIGNER_UNIT"
PUB=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close();assert r.get('version')=='4.0' and r.get('mode')=='READY' and r.get('walletLoaded') is True and r.get('signingEnabled') is False and r.get('arbitraryRawSign') is False;print(r['publicKey'])
PY
)
echo "BOT_PUBLIC_KEY=$PUB"
echo SIGNER_VERSION=4.0
echo SIGNER_MODE=READY_LOCKED

getbal(){ python3 - "$RPC" "$PUB" <<'PY'
import json,sys,urllib.request
rpc,pub=sys.argv[1:];d=json.dumps({'jsonrpc':'2.0','id':1,'method':'getBalance','params':[pub,{'commitment':'confirmed'}]}).encode();q=urllib.request.Request(rpc,data=d,headers={'content-type':'application/json','user-agent':'meme-alpha-v251'})
with urllib.request.urlopen(q,timeout=12) as r:j=json.loads(r.read())
if 'error' in j:raise SystemExit('RPC_BALANCE_ERROR')
print(int(j['result']['value']))
PY
}
BAL=$(getbal)
printf 'BOT_BALANCE_SOL=%.9f\n' "$(python3 -c "print($BAL/1000000000)")"
if [ "$BAL" -lt 30000000 ]; then
  echo LIVE_ACTIVATION=WAITING_FOR_FUNDING
  echo RECOMMENDED_INITIAL_FUNDING_SOL=0.050
  echo REQUIRED_INITIAL_RANGE_SOL=0.030_TO_0.100
  echo "SEND_SOL_TO=$PUB"
  echo WAITING_UP_TO_30_MINUTES=TRUE
  for _ in $(seq 1 180); do
    sleep 10
    BAL=$(getbal || echo 0)
    if [ "$BAL" -ge 30000000 ]; then break; fi
  done
fi
[ "$BAL" -ge 30000000 ] || { echo ABORT_FUNDING_NOT_RECEIVED_WITHIN_30_MINUTES; exit 1; }
[ "$BAL" -le 100000000 ] || { echo ABORT_INITIAL_BALANCE_GT_0_10_SOL;echo MOVE_EXCESS_OUT_BEFORE_FIRST_ACTIVATION=TRUE;exit 1; }
printf 'FUNDED_BALANCE_SOL=%.9f\n' "$(python3 -c "print($BAL/1000000000)")"

printf 'ARMED=YES\n' > "$ETC/signer-enabled";printf 'ARMED=YES\n' > "$ETC/micro-live-armed";printf 'MICRO_LIVE\n' > "$ETC/execution-mode"
for f in signer-enabled micro-live-armed execution-mode;do chown root:meme-alpha-signer-client "$ETC/$f";chmod 640 "$ETC/$f";done
rollback(){ systemctl disable --now "$MICRO_UNIT" >/dev/null 2>&1 || true;rm -f "$ETC/signer-enabled" "$ETC/micro-live-armed" "$ETC/execution-mode";echo LIVE_ACTIVATION_ROLLBACK=APPLIED >&2; }
trap rollback ERR
sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close();assert r.get('version')=='4.0' and r.get('mode')=='READY' and r.get('walletLoaded') is True and r.get('signingEnabled') is True and r.get('arbitraryRawSign') is False
print('SIGNER_ARMED=TRUE');print('SIGNER_BUY_POLICY='+str(r.get('buyPolicy')));print('ARBITRARY_RAW_SIGN=FALSE')
PY

# Do not require a trade candidate at activation time. We only require the gate to
# observe the root controls and armed signer. The executor itself remains fail-closed
# and will WAIT until gate.allowed=true.
seen=0
for _ in $(seq 1 45);do
  sleep 4
  if [ -f "$GATE" ] && python3 - <<'PY'
import json,sys
try:x=json.load(open('/opt/meme-alpha/app/runtime-status/micro-live-gate.json'))
except:sys.exit(1)
ok=x.get('version')=='2.4.0' and x.get('executionMode')=='MICRO_LIVE' and x.get('armOk') is True and x.get('signer',{}).get('signingEnabled') is True and x.get('signer',{}).get('walletLoaded') is True
sys.exit(0 if ok else 1)
PY
  then seen=1;break;fi
done
[ "$seen" -eq 1 ] || { echo ABORT_GATE_DID_NOT_OBSERVE_ARMED_CONTROLS;false; }
systemctl enable --now "$MICRO_UNIT";sleep 2;systemctl is-active --quiet "$MICRO_UNIT"
trap - ERR

python3 - <<'PY'
import json
x=json.load(open('/opt/meme-alpha/app/runtime-status/micro-live-gate.json'))
print('MICRO_LIVE_GATE_ALLOWED='+str(bool(x.get('allowed'))).lower())
print('MICRO_LIVE_GATE_REASONS='+(','.join(x.get('reasons',[])) or 'NONE'))
print('LIVE_STATE='+('ACTIVE_SAFE_GATE_OPEN' if x.get('allowed') else 'ARMED_WAITING_FOR_SAFE_GATE'))
PY

echo MICRO_EXECUTOR_ACTIVE=TRUE
echo CAPITAL_FLOW_AWARE=TRUE
echo DEPOSIT_AUTO_RESIZES_FUTURE_ENTRIES=TRUE
echo WITHDRAWAL_AUTO_RESIZES_FUTURE_ENTRIES=TRUE
echo PRE_EVIDENCE_ENTRY_CAP_SOL=0.005
echo POST_EVIDENCE_BASE_UTILIZATION_PCT=70
echo POST_EVIDENCE_STRONG_UTILIZATION_PCT=82
echo POST_EVIDENCE_MAX_UTILIZATION_PCT=90
echo MIN_POST_EVIDENCE_RESERVE_SOL=0.010
echo SIGNER_DYNAMIC_BALANCE_LIMIT=TRUE
echo SIGNER_REQUIRES_FRESH_ELIGIBLE_SIGNAL_FOR_BUY=TRUE
echo REAL_NETWORK_EXECUTION=ONLY_WHEN_GATE_AND_SIGNAL_ELIGIBLE
echo V251_REAL_MICRO_LIVE_ARMED_PASS
