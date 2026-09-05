#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
systemctl disable --now meme-alpha-micro-live.service 2>/dev/null || true
rm -f /etc/meme-alpha/execution-mode /etc/meme-alpha/micro-live-armed /etc/meme-alpha/signer-enabled
# Signer reads the root arming file on every signing request, so removing it locks immediately.
sleep 1
if systemctl is-active --quiet meme-alpha-micro-live.service; then echo FAIL_EXECUTOR_ACTIVE; exit 1; fi
sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(4096));s.close();assert r.get('signingEnabled') is False;print('SIGNING_ENABLED=false')
PY
echo EXECUTION_MODE=DISABLED
echo MICRO_LIVE_ARMED=FALSE
echo EMERGENCY_DISARM=PASS
