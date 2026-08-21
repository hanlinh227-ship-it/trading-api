#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/opt/trading/trading-api"
WORKER="$ROOT/signal-only-v10/ai_council_worker.py"
[[ -f "$WORKER" ]] || { echo "missing $WORKER"; exit 2; }
chmod 700 "$WORKER"
python3 -m py_compile "$WORKER"
cat > /etc/systemd/system/signal-v10-council.service <<'EOF'
[Unit]
Description=Signal Only V10 Three-AI Council Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trading/trading-api
EnvironmentFile=-/opt/trading/.env.ai
EnvironmentFile=-/opt/trading/.env.telegram
ExecStart=/usr/bin/python3 /opt/trading/trading-api/signal-only-v10/ai_council_worker.py
Restart=always
RestartSec=5
NoNewPrivileges=true
Nice=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now signal-v10-council.service
echo "SIGNAL_V10_COUNCIL=$(systemctl is-active signal-v10-council.service || true)"
