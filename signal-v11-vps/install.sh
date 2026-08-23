#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/trading-api
cd "$ROOT"
git fetch origin main
git checkout main
git pull --ff-only origin main
python3 -m py_compile signal-v11-vps/manual_ai_bridge.py
install -m 0755 signal-v11-vps/manual_ai_bridge.py /usr/local/bin/v11-manual-ai-bridge
cat >/etc/systemd/system/v11-manual-ai-bridge.service <<'EOF'
[Unit]
Description=V11 five-provider Multi-AI bridge
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
V11_AI_TIMEOUT=120
EOF
  chmod 600 /etc/trading-v11-ai.env
fi
command -v claude >/dev/null || { echo 'ERROR: claude CLI missing'; exit 2; }
test -x /usr/bin/codex || { echo 'ERROR: /usr/bin/codex missing'; exit 3; }
set -a
source /etc/trading-v11-ai.env
set +a
test -n "${DEEPSEEK_API_KEY:-}" || { echo 'ERROR: DEEPSEEK_API_KEY missing'; exit 4; }
test -n "${QWEN_API_KEY:-}" || { echo 'ERROR: QWEN_API_KEY missing'; exit 5; }
test -n "${OPENROUTER_API_KEY:-}" || { echo 'ERROR: OPENROUTER_API_KEY missing'; exit 6; }
claude --version
/usr/bin/codex --version
systemctl daemon-reload
systemctl restart v11-manual-ai-bridge
systemctl enable v11-manual-ai-bridge
sleep 3
HEALTH="$(curl -fsS http://127.0.0.1:8789/health)"
printf '%s\n' "$HEALTH" | python3 -c 'import json,sys; d=json.load(sys.stdin); exp={"claude","codex","deepseek","qwen","openrouter"}; p=d.get("providers") or {}; miss=exp-set(p); assert not miss, f"missing providers: {sorted(miss)}"; assert all(bool((p[n] or {}).get("configured")) for n in exp), "one or more providers not configured"; print("V11_MULTI_AI_BRIDGE_HEALTH=PASS providers="+",".join(sorted(exp)))'
printf '\nV11 five-provider bridge installed from GitHub main. Port 8789 remains localhost/private and is reached by Cloudflare AI_BRIDGE VPC only.\n'
