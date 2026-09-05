#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STATUS=$APP/runtime-status
KEYDIR=/var/lib/meme-alpha-signer/keys
KEY=$KEYDIR/bot-keypair.json
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
python3 - <<'PY'
import json,sys
R='/opt/meme-alpha/app/runtime-status/'
v=json.load(open(R+'validation.json'));s=json.load(open(R+'stress-test.json'));u=json.load(open(R+'universe.json'));g=json.load(open(R+'micro-live-gate.json'))
assert v.get('readinessStatus')=='PASS','ABORT_VALIDATION_NOT_PASS'
assert int(v.get('completedLifecycleTrades',0))>=20,'ABORT_LIFECYCLES_LT_20'
assert s.get('status')=='PASS' and int(s.get('fail',1))==0,'ABORT_STRESS_NOT_PASS'
assert u.get('version')=='1.6' and u.get('unknownEntryEligible') is False,'ABORT_UNIVERSE_NOT_PASS'
assert g.get('analysisMode')=='PAPER','ABORT_ANALYSIS_MODE_NOT_PAPER'
print('EMPIRICAL_VALIDATION=PASS');print('STRESS=PASS');print('POSITIVE_MEME_GATE=PASS')
PY
[ -x /opt/meme-alpha-signer/ready_signer.py ] || { echo ABORT_READY_SIGNER_NOT_INSTALLED; exit 1; }
install -d -o meme-alpha-signer -g meme-alpha-signer -m 0700 "$KEYDIR"
if [ -e "$KEY" ]; then echo ABORT_WALLET_ALREADY_EXISTS; exit 1; fi
rm -f /etc/meme-alpha/signer-enabled /etc/meme-alpha/micro-live-armed /etc/meme-alpha/execution-mode
python3 - <<'PY'
import json,os,subprocess,tempfile
key='/var/lib/meme-alpha-signer/keys/bot-keypair.json'
seed=os.urandom(32)
der=bytes.fromhex('302e020100300506032b657004220420')+seed
p=subprocess.run(['openssl','pkey','-inform','DER','-pubout','-outform','DER'],input=der,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
pub=p.stdout[-32:]
if len(pub)!=32: raise SystemExit('PUBKEY_DER_FAIL')
raw=list(seed+pub)
tmp=key+'.tmp';open(tmp,'w').write(json.dumps(raw,separators=(',',':'))+'\n');os.chmod(tmp,0o600);os.replace(tmp,key)
PY
chown meme-alpha-signer:meme-alpha-signer "$KEY"; chmod 600 "$KEY"
systemctl restart meme-alpha-signer.service
sleep 1
systemctl is-active --quiet meme-alpha-signer.service
sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(4096));s.close();assert r.get('walletLoaded') is True and r.get('signingEnabled') is False and r.get('mode')=='READY';print('BOT_PUBLIC_KEY='+r['publicKey']);print('SIGNER_MODE=READY');print('WALLET_LOADED=true');print('SIGNING_ENABLED=false')
PY
if sudo -u github-runner test -r "$KEY"; then echo FAIL_RUNNER_KEY_READ; exit 1; fi
echo RUNNER_KEY_ACCESS=DENIED_PASS
echo WALLET_CREATED=TRUE
echo WALLET_FUNDED=FALSE
echo MICRO_LIVE_ARMED=FALSE
echo V180_WALLET_CREATED_LOCKED_PASS
