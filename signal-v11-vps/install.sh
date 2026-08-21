#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/trading-api
cd "$ROOT"
git fetch origin
git checkout signal-v11
git pull --ff-only origin signal-v11
install -m 0755 signal-v11-vps/manual_ai_bridge.py /usr/local/bin/v11-manual-ai-bridge
cat >/etc/systemd/system/v11-manual-ai-bridge.service <<'EOF'
[Unit]
Description=V11 on-demand Claude Codex bridge
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=root
EnvironmentFile=/etc/trading-v11-ai.env
ExecStart=/usr/bin/python3 /usr/local/bin/v11-manual-ai-bridge
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths=/tmp /root/.config /root/.cache
[Install]
WantedBy=multi-user.target
EOF
if [ ! -f /etc/trading-v11-ai.env ]; then
  SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
  cat >/etc/trading-v11-ai.env <<EOF
V11_AI_BRIDGE_SECRET=$SECRET
V11_AI_BRIDGE_HOST=127.0.0.1
V11_AI_BRIDGE_PORT=8789
V11_CLAUDE_MODEL=sonnet
V11_CODEX_MODEL=gpt-5.6-sol
V11_AI_TIMEOUT=60
EOF
  chmod 600 /etc/trading-v11-ai.env
fi
command -v claude >/dev/null || { echo 'ERROR: claude CLI missing'; exit 2; }
test -x /usr/bin/codex || { echo 'ERROR: /usr/bin/codex missing'; exit 3; }
claude --version
/usr/bin/codex --version
systemctl daemon-reload
systemctl enable --now v11-manual-ai-bridge
sleep 2
curl -fsS http://127.0.0.1:8789/health
printf '\nV11 bridge installed. Keep port 8789 private; expose it through the existing authenticated Cloudflare/VPS tunnel and set Worker secrets V11_AI_BRIDGE_URL + V11_AI_BRIDGE_SECRET.\n'
