#!/usr/bin/env bash
set -euo pipefail
SRC=/opt/meme-alpha/app/ops/security/ready_signer.py
DST=/opt/meme-alpha-signer/ready_signer.py
UNIT=/etc/systemd/system/meme-alpha-signer.service
POLICY=/etc/meme-alpha/signer-policy.json
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
[ -f "$SRC" ] || { echo ABORT_READY_SIGNER_NOT_STAGED; exit 1; }
python3 - <<'PY'
import json
c=json.load(open('/opt/meme-alpha/app/config/runtime.json'))
assert c.get('mode')=='PAPER','ABORT_NOT_PAPER'
print('ANALYSIS_MODE=PAPER');print('LIVE_EXECUTION=DISABLED')
PY
runner=$(systemctl show actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service -p User --value)
[ "$runner" = github-runner ] || { echo "ABORT_RUNNER=$runner"; exit 1; }
install -o root -g root -m 0555 "$SRC" "$DST"
install -d -o root -g meme-alpha-signer-client -m 0750 /etc/meme-alpha
cat > "$POLICY" <<'JSON'
{
  "maxBuyLamports": 20000000,
  "dailyBuyLamports": 50000000,
  "maxOrdersPerHour": 5,
  "maxPriceImpactPct": 1.5,
  "jupiterBaseUrl": "https://api.jup.ag"
}
JSON
chown root:meme-alpha-signer-client "$POLICY"; chmod 640 "$POLICY"
rm -f /etc/meme-alpha/signer-enabled /etc/meme-alpha/micro-live-armed /etc/meme-alpha/execution-mode
cat > "$UNIT" <<'EOF'
[Unit]
Description=Meme Alpha isolated Jupiter-only signer
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=meme-alpha-signer
Group=meme-alpha-signer-client
ExecStart=/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py
Restart=on-failure
RestartSec=2
UMask=0007
RuntimeDirectory=meme-alpha-signer
RuntimeDirectoryMode=0750
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
MemoryDenyWriteExecute=true
ReadOnlyPaths=/opt/meme-alpha-signer /etc/meme-alpha
ReadWritePaths=/run/meme-alpha-signer /var/lib/meme-alpha-signer
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl restart meme-alpha-signer.service
sleep 1
systemctl is-active --quiet meme-alpha-signer.service
sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(4096));s.close();assert r['ok'] is True; assert r['signingEnabled'] is False; assert r.get('arbitraryRawSign') is False; print('BOT_SIGNER_HEALTH=PASS');print('SIGNER_VERSION='+str(r.get('version')));print('SIGNER_MODE='+str(r.get('mode')));print('WALLET_LOADED='+str(r.get('walletLoaded')).lower());print('SIGNING_ENABLED=false');print('ARBITRARY_RAW_SIGN=false')
PY
if sudo -u github-runner test -r /var/lib/meme-alpha-signer/keys || sudo -u github-runner test -x /var/lib/meme-alpha-signer/keys; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; fi
if sudo -u github-runner test -w /run/meme-alpha-signer/signer.sock; then echo FAIL_RUNNER_SOCKET_ACCESS; exit 1; fi
echo GITHUB_RUNNER_KEY_ACCESS=DENIED_PASS
echo GITHUB_RUNNER_SIGNER_SOCKET=DENIED_PASS
echo MAX_BUY_SOL=0.02
echo DAILY_BUY_CAP_SOL=0.05
echo MAX_ORDERS_PER_HOUR=5
echo WALLET_CREATED=FALSE
echo SIGNING_ARMED=FALSE
echo V170_READY_SIGNER_INSTALLED_LOCKED_PASS
