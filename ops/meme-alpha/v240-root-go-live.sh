#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
ETC=/etc/meme-alpha
KEYDIR=/var/lib/meme-alpha-signer/keys
KEY=$KEYDIR/bot-keypair.json
SIGNER_UNIT=meme-alpha-signer.service
MICRO_UNIT=meme-alpha-micro-live.service
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
GATE=$APP/runtime-status/micro-live-gate.json

[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"

echo '=== MEME ALPHA v2.4.0 ROOT LIVE ACTIVATION ==='

# The analysis engine deliberately remains PAPER so scanner/risk/signal production never stops.
python3 - <<'PY'
import json
c=json.load(open('/opt/meme-alpha/app/config/runtime.json'))
assert c.get('mode')=='PAPER','ABORT_ANALYSIS_ENGINE_NOT_PAPER'
print('ANALYSIS_ENGINE=PAPER_CONTINUOUS')
PY

[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_NOT_ISOLATED; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service || { echo ABORT_PAPER_SIGNAL_ENGINE_INACTIVE; exit 1; }
systemctl is-active --quiet "$SIGNER_UNIT" || { echo ABORT_SIGNER_INACTIVE; exit 1; }
[ -f /etc/systemd/system/$MICRO_UNIT ] || { echo ABORT_MICRO_EXECUTOR_NOT_INSTALLED; exit 1; }
[ -f "$APP/src/micro-live-gate.js" ] || { echo ABORT_V240_GATE_NOT_INSTALLED; exit 1; }
grep -q "version:'2.4.0'" "$APP/src/micro-live-gate.js" || { echo ABORT_V240_GATE_NOT_INSTALLED; exit 1; }

# Runner must remain unable to read signing material or call the signer directly.
if sudo -u github-runner test -r "$KEYDIR" || sudo -u github-runner test -x "$KEYDIR"; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if sudo -u github-runner test -r /run/meme-alpha-signer/signer.sock || sudo -u github-runner test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi
echo RUNNER_ISOLATION=PASS

# Always start activation from a locked state. Existing wallet is preserved.
rm -f "$ETC/signer-enabled" "$ETC/micro-live-armed" "$ETC/execution-mode"
systemctl disable --now "$MICRO_UNIT" >/dev/null 2>&1 || true

install -d -o meme-alpha-signer -g meme-alpha-signer -m 0700 "$KEYDIR"
if [ ! -f "$KEY" ]; then
  python3 - <<'PY'
import json,os,subprocess
key='/var/lib/meme-alpha-signer/keys/bot-keypair.json'
seed=os.urandom(32)
der=bytes.fromhex('302e020100300506032b657004220420')+seed
p=subprocess.run(['openssl','pkey','-inform','DER','-pubout','-outform','DER'],input=der,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=5)
pub=p.stdout[-32:]
if len(pub)!=32: raise SystemExit('PUBKEY_DER_FAIL')
tmp=key+'.tmp'
with open(tmp,'w') as f: json.dump(list(seed+pub),f,separators=(',',':'))
os.chmod(tmp,0o600)
os.replace(tmp,key)
PY
  chown meme-alpha-signer:meme-alpha-signer "$KEY"
  chmod 600 "$KEY"
  echo WALLET_CREATED=TRUE
else
  [ "$(stat -c %U:%G "$KEY")" = meme-alpha-signer:meme-alpha-signer ] || { echo ABORT_WALLET_OWNER; exit 1; }
  [ "$(stat -c %a "$KEY")" = 600 ] || { echo ABORT_WALLET_MODE; exit 1; }
  echo WALLET_CREATED=ALREADY_EXISTS
fi

systemctl restart "$SIGNER_UNIT"
sleep 1
systemctl is-active --quiet "$SIGNER_UNIT"

PUB=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close()
assert r.get('ok') is True and r.get('mode')=='READY' and r.get('walletLoaded') is True and r.get('signingEnabled') is False,'SIGNER_NOT_READY_LOCKED'
print(r['publicKey'])
PY
)
echo "BOT_PUBLIC_KEY=$PUB"
echo SIGNER_MODE=READY_LOCKED

RPC=$(python3 - <<'PY'
import json
print(json.load(open('/opt/meme-alpha/app/config/runtime.json')).get('rpc','https://api.mainnet-beta.solana.com'))
PY
)
BAL=$(python3 - "$RPC" "$PUB" <<'PY'
import json,sys,urllib.request
rpc,pub=sys.argv[1:]
data=json.dumps({'jsonrpc':'2.0','id':1,'method':'getBalance','params':[pub,{'commitment':'confirmed'}]}).encode()
req=urllib.request.Request(rpc,data=data,headers={'content-type':'application/json','user-agent':'meme-alpha-v240'})
with urllib.request.urlopen(req,timeout=12) as r:j=json.loads(r.read())
if 'error' in j: raise SystemExit('RPC_BALANCE_ERROR')
print(int(j['result']['value']))
PY
)
python3 - "$BAL" <<'PY'
import sys
b=int(sys.argv[1]);print(f'BOT_BALANCE_SOL={b/1_000_000_000:.9f}')
PY

# First invocation deliberately stops here until the user funds the newly created dedicated wallet.
if [ "$BAL" -lt 30000000 ]; then
  echo LIVE_ACTIVATION=WAITING_FOR_FUNDING
  echo REQUIRED_BALANCE_SOL_MIN=0.030
  echo RECOMMENDED_FUNDING_SOL=0.050
  echo MAX_ACTIVATION_BALANCE_SOL=0.100
  echo SIGNER_ARMED=FALSE
  echo MICRO_EXECUTOR_ACTIVE=FALSE
  echo 'NEXT_ACTION=FUND_BOT_PUBLIC_KEY_THEN_RUN_THIS_SAME_SCRIPT_AGAIN'
  exit 0
fi
if [ "$BAL" -gt 100000000 ]; then
  echo ABORT_MICRO_WALLET_BALANCE_GT_0_10_SOL
  echo 'MOVE_EXCESS_OUT_BEFORE_ACTIVATION=TRUE'
  exit 1
fi

# Statistical sample count is no longer a blocker for real micro trading.
# Known validation/stress failures still remain fail-closed in the v2.4.0 gate.
install -d -o root -g meme-alpha-signer-client -m 0750 "$ETC"
printf 'ARMED=YES\n' > "$ETC/signer-enabled"
printf 'ARMED=YES\n' > "$ETC/micro-live-armed"
printf 'MICRO_LIVE\n' > "$ETC/execution-mode"
for f in signer-enabled micro-live-armed execution-mode; do chown root:meme-alpha-signer-client "$ETC/$f"; chmod 640 "$ETC/$f"; done

rollback(){
  systemctl disable --now "$MICRO_UNIT" >/dev/null 2>&1 || true
  rm -f "$ETC/signer-enabled" "$ETC/micro-live-armed" "$ETC/execution-mode"
  echo LIVE_ACTIVATION_ROLLBACK=APPLIED >&2
}
trap rollback ERR

# Signer policy checks the root arming file dynamically.
sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close()
assert r.get('ok') is True and r.get('mode')=='READY' and r.get('walletLoaded') is True and r.get('signingEnabled') is True,'SIGNER_DID_NOT_ARM'
assert r.get('arbitraryRawSign') is False,'ARBITRARY_RAW_SIGN_MUST_BE_FALSE'
print('SIGNER_ARMED=TRUE')
print('ARBITRARY_RAW_SIGN=FALSE')
PY

# Wait only for the next normal signal/risk cycle; no additional test cycles are forced.
opened=0
for _ in $(seq 1 45); do
  sleep 4
  if [ -f "$GATE" ] && python3 - <<'PY'
import json,sys
p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json'
try:x=json.load(open(p))
except:sys.exit(1)
sys.exit(0 if x.get('version')=='2.4.0' and x.get('allowed') is True else 1)
PY
  then opened=1; break; fi
done
[ "$opened" -eq 1 ] || {
  python3 - <<'PY'
import json
p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json'
try:
 x=json.load(open(p));print('GATE_REASONS='+','.join(x.get('reasons',[])))
except Exception as e: print('GATE_READ_ERROR='+type(e).__name__)
PY
  echo ABORT_GATE_NOT_READY
  false
}

systemctl enable --now "$MICRO_UNIT"
sleep 2
systemctl is-active --quiet "$MICRO_UNIT"
trap - ERR

echo MICRO_LIVE_GATE=PASS
echo MICRO_EXECUTOR_ACTIVE=TRUE
echo REAL_NETWORK_EXECUTION=ENABLED_WHEN_SIGNAL_ELIGIBLE
echo PAPER_SAMPLE_COUNT_BLOCKER=REMOVED_FOR_MICRO_LIVE
echo SCALE_GATE_20_LIFECYCLES=RETAINED
echo V240_REAL_MICRO_LIVE_ACTIVE=PASS
