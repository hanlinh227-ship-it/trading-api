#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
ETC=/etc/meme-alpha
UNIT=meme-alpha-micro-live.service
rollback(){
  rm -f "$ETC/signer-enabled" "$ETC/micro-live-armed" "$ETC/execution-mode"
  systemctl disable --now "$UNIT" >/dev/null 2>&1 || true
  systemctl restart meme-alpha-signer.service >/dev/null 2>&1 || true
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; echo MICRO_LIVE_ROLLBACK=PASS; fi; exit $rc' EXIT
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
[ -f "$APP/src/micro-live-executor.js" ] || { echo ABORT_EXECUTOR_NOT_INSTALLED; exit 1; }
[ -f /var/lib/meme-alpha-signer/keys/bot-keypair.json ] || { echo ABORT_NO_WALLET; exit 1; }
python3 - <<'PY'
import json
R='/opt/meme-alpha/app/runtime-status/'
v=json.load(open(R+'validation.json'));s=json.load(open(R+'stress-test.json'));u=json.load(open(R+'universe.json'))
assert v.get('readinessStatus')=='PASS' and int(v.get('completedLifecycleTrades',0))>=20,'ABORT_VALIDATION'
assert s.get('status')=='PASS' and int(s.get('fail',1))==0,'ABORT_STRESS'
assert u.get('version')=='1.6' and u.get('unknownEntryEligible') is False,'ABORT_UNIVERSE'
print('VALIDATION=PASS');print('STRESS=PASS');print('UNIVERSE=PASS')
PY
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
PUB=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(4096));s.close();assert r.get('mode')=='READY' and r.get('walletLoaded') is True and r.get('signingEnabled') is False;print(r['publicKey'])
PY
)
RPC=$(python3 - <<'PY'
import json;print(json.load(open('/opt/meme-alpha/app/config/runtime.json')).get('rpc','https://api.mainnet-beta.solana.com'))
PY
)
BAL=$(python3 - "$RPC" "$PUB" <<'PY'
import json,sys,urllib.request
rpc,pub=sys.argv[1:];data=json.dumps({'jsonrpc':'2.0','id':1,'method':'getBalance','params':[pub,{'commitment':'confirmed'}]}).encode();req=urllib.request.Request(rpc,data=data,headers={'content-type':'application/json'})
with urllib.request.urlopen(req,timeout=10) as r:j=json.loads(r.read())
if 'error' in j:raise SystemExit('RPC_BALANCE_ERROR')
print(int(j['result']['value']))
PY
)
python3 - "$BAL" <<'PY'
import sys
b=int(sys.argv[1]);print(f'WALLET_BALANCE_SOL={b/1e9:.9f}');assert b>=30_000_000,'ABORT_MICRO_BALANCE_LT_0_03_SOL';assert b<=100_000_000,'ABORT_MICRO_BALANCE_GT_0_10_SOL'
PY
install -d -o root -g meme-alpha-signer-client -m 0750 "$ETC"
# Policy must pre-exist from v1.9.2 installer and stay root-controlled.
python3 - <<'PY'
import json,os
p='/etc/meme-alpha/micro-live-policy.json';st=os.stat(p);x=json.load(open(p));assert st.st_uid==0 and (st.st_mode&0o777)==0o640;assert 1_000_000<=int(x['maxEntryLamports'])<=5_000_000;assert int(x['minReserveLamports'])>=20_000_000;assert float(x['maxPriceImpactPct'])<=1.25
print('MICRO_POLICY=PASS')
PY
printf 'ARMED=YES\n' > "$ETC/signer-enabled"
printf 'ARMED=YES\n' > "$ETC/micro-live-armed"
printf 'MICRO_LIVE\n' > "$ETC/execution-mode"
for f in signer-enabled micro-live-armed execution-mode; do chown root:meme-alpha-signer-client "$ETC/$f"; chmod 640 "$ETC/$f"; done
systemctl restart meme-alpha-signer.service
sleep 2
# Wait for PAPER cycle to recompute gate with root-controlled execution mode.
for i in $(seq 1 12); do
  if python3 - <<'PY'
import json
x=json.load(open('/opt/meme-alpha/app/runtime-status/micro-live-gate.json'));raise SystemExit(0 if x.get('allowed') is True else 1)
PY
  then break; fi
  sleep 10
done
python3 - <<'PY'
import json
x=json.load(open('/opt/meme-alpha/app/runtime-status/micro-live-gate.json'));print('GATE_ALLOWED='+str(x.get('allowed')).lower());print('GATE_REASONS='+','.join(x.get('reasons',[])));assert x.get('allowed') is True,'ABORT_GATE_DID_NOT_OPEN'
PY
systemctl enable --now "$UNIT"
sleep 3
systemctl is-active --quiet "$UNIT"
systemctl is-enabled --quiet "$UNIT"
echo BOT_PUBLIC_KEY="$PUB"
echo EXECUTION_MODE=MICRO_LIVE
echo MICRO_EXECUTOR_ACTIVE=TRUE
echo V193_MICRO_LIVE_ARM_PASS
trap - EXIT
