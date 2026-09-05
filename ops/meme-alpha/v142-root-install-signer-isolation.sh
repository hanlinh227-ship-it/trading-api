#!/usr/bin/env bash
set -euo pipefail

SRC=/opt/meme-alpha/app/ops/security/locked_signer.py
SIGNER_ROOT=/opt/meme-alpha-signer
KEY_ROOT=/var/lib/meme-alpha-signer/keys
UNIT=/etc/systemd/system/meme-alpha-signer.service
SIGNER_USER=meme-alpha-signer
SIGNER_GROUP=meme-alpha-signer
CLIENT_GROUP=meme-alpha-signer-client

[ "$(id -u)" -eq 0 ] || { echo 'ABORT_ROOT_REQUIRED'; exit 1; }
[ -f "$SRC" ] || { echo "ABORT_STAGED_SIGNER_MISSING=$SRC"; exit 1; }

# Existing trading runtime must remain paper-only during signer isolation setup.
python3 - <<'PY'
import json
p='/opt/meme-alpha/app/config/runtime.json'
with open(p,'r',encoding='utf-8') as f: c=json.load(f)
if c.get('mode') != 'PAPER': raise SystemExit('ABORT_NOT_PAPER')
print('MODE=PAPER')
print('LIVE_EXECUTION=DISABLED')
PY

runner_user=$(systemctl show actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service -p User --value)
[ "$runner_user" = github-runner ] || { echo "ABORT_RUNNER_USER=$runner_user"; exit 1; }

if ! getent group "$SIGNER_GROUP" >/dev/null; then groupadd --system "$SIGNER_GROUP"; fi
if ! id "$SIGNER_USER" >/dev/null 2>&1; then
  useradd --system --gid "$SIGNER_GROUP" --home-dir /var/lib/meme-alpha-signer --shell /usr/sbin/nologin "$SIGNER_USER"
fi
if ! getent group "$CLIENT_GROUP" >/dev/null; then groupadd --system "$CLIENT_GROUP"; fi
usermod -a -G "$CLIENT_GROUP" "$SIGNER_USER"
usermod -a -G "$CLIENT_GROUP" meme-alpha

# GitHub runner must never join the signer client group.
if id -nG github-runner | tr ' ' '\n' | grep -qx "$CLIENT_GROUP"; then
  gpasswd -d github-runner "$CLIENT_GROUP" >/dev/null 2>&1 || true
fi

install -d -o root -g root -m 0755 "$SIGNER_ROOT"
install -o root -g root -m 0555 "$SRC" "$SIGNER_ROOT/locked_signer.py"
install -d -o "$SIGNER_USER" -g "$SIGNER_GROUP" -m 0700 /var/lib/meme-alpha-signer
install -d -o "$SIGNER_USER" -g "$SIGNER_GROUP" -m 0700 "$KEY_ROOT"

# No key is created here. If a key somehow exists already, stop rather than touching it.
key_count=$(find "$KEY_ROOT" -maxdepth 1 -type f | wc -l)
[ "$key_count" -eq 0 ] || { echo "ABORT_UNEXPECTED_SIGNER_KEY_FILES=$key_count"; exit 1; }

cat > "$UNIT" <<EOF
[Unit]
Description=Meme Alpha isolated signer (LOCKED preflight)
After=network.target

[Service]
Type=simple
User=$SIGNER_USER
Group=$CLIENT_GROUP
ExecStart=/usr/bin/python3 $SIGNER_ROOT/locked_signer.py
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
RestrictAddressFamilies=AF_UNIX
LockPersonality=true
MemoryDenyWriteExecute=true
ReadOnlyPaths=$SIGNER_ROOT
ReadWritePaths=/run/meme-alpha-signer /var/lib/meme-alpha-signer

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now meme-alpha-signer.service >/dev/null
sleep 1
systemctl is-active --quiet meme-alpha-signer.service

echo '=== SIGNER ISOLATION VERIFY ==='
echo "SIGNER_USER=$(systemctl show meme-alpha-signer.service -p User --value)"
echo "SIGNER_GROUP=$(systemctl show meme-alpha-signer.service -p Group --value)"
echo "KEY_DIR_OWNER=$(stat -c %U:%G "$KEY_ROOT")"
echo "KEY_DIR_MODE=$(stat -c %a "$KEY_ROOT")"
echo "KEY_FILE_COUNT=$key_count"

if sudo -u github-runner test -r "$KEY_ROOT" || sudo -u github-runner test -x "$KEY_ROOT"; then
  echo 'FAIL_GITHUB_RUNNER_CAN_ACCESS_SIGNER_KEYS'
  exit 1
else
  echo 'GITHUB_RUNNER_KEY_ACCESS=DENIED_PASS'
fi

if sudo -u github-runner test -r /run/meme-alpha-signer/signer.sock || sudo -u github-runner test -w /run/meme-alpha-signer/signer.sock; then
  echo 'FAIL_GITHUB_RUNNER_CAN_ACCESS_SIGNER_SOCKET'
  exit 1
else
  echo 'GITHUB_RUNNER_SIGNER_SOCKET=DENIED_PASS'
fi

sudo -u meme-alpha python3 - <<'PY'
import json, socket
p='/run/meme-alpha-signer/signer.sock'
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(2); s.connect(p)
s.sendall(b'{"op":"health"}\n')
data=s.recv(4096).decode().strip(); s.close()
r=json.loads(data)
assert r.get('ok') is True
assert r.get('mode') == 'LOCKED'
assert r.get('signingEnabled') is False
assert r.get('walletLoaded') is False
print('BOT_TO_SIGNER_HEALTH=PASS')
print('SIGNER_MODE=LOCKED')
print('SIGNING_ENABLED=false')
print('WALLET_LOADED=false')
PY

sudo -u meme-alpha python3 - <<'PY'
import json, socket
p='/run/meme-alpha-signer/signer.sock'
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(2); s.connect(p)
s.sendall(b'{"op":"sign","transaction":"not-a-real-transaction"}\n')
data=s.recv(4096).decode().strip(); s.close()
r=json.loads(data)
assert r.get('ok') is False
assert r.get('error') == 'SIGNING_LOCKED'
print('SIGN_REQUEST_BLOCKED=PASS')
PY

systemctl is-active --quiet meme-alpha-paper.service
echo 'PAPER_SERVICE_ACTIVE=PASS'
echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_SECRET_REQUIRED=TRUE'
echo 'V142_SIGNER_ISOLATION_LOCKED_PASS'
