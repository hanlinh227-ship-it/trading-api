#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
systemctl disable --now meme-alpha-micro-live.service 2>/dev/null || true
rm -f /etc/meme-alpha/signer-enabled /etc/meme-alpha/micro-live-armed /etc/meme-alpha/execution-mode
systemctl restart meme-alpha-signer.service
sleep 2
! systemctl is-active --quiet meme-alpha-micro-live.service
sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(4096));s.close();assert r.get('signingEnabled') is False;print('SIGNING_ENABLED=false')
PY
echo MICRO_EXECUTOR_ACTIVE=FALSE
echo EXECUTION_MODE=DISABLED
echo V194_EMERGENCY_DISARM_PASS
