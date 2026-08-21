#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/opt/trading/trading-api"
BOT="$ROOT/auto-futures-v1"

if [[ ! -f /opt/trading/.env.telegram ]]; then
  cat > /opt/trading/.env.telegram <<'EOF'
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
TELEGRAM_ALLOWED_USER_ID=""
EOF
  chmod 600 /opt/trading/.env.telegram
  echo "CREATED /opt/trading/.env.telegram - fill Telegram values before starting hub"
fi

cat > /etc/systemd/system/auto-futures-telegram.service <<'EOF'
[Unit]
Description=Auto Futures V6 Telegram Approval Hub
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trading/trading-api
EnvironmentFile=-/opt/trading/.env.ai
EnvironmentFile=-/opt/trading/.env.binance
EnvironmentFile=-/opt/trading/.env.telegram
ExecStart=/usr/bin/python3 /opt/trading/trading-api/auto-futures-v1/execution/telegram_hub.py
Restart=always
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

# Scalp re-evaluation cadence: every 60 seconds. Telegram confirmation TTLs are shorter
# and each click performs an immediate fresh scanner+3AI+risk+guard revalidation.
cat > /etc/systemd/system/auto-futures-scan.timer <<'EOF'
[Unit]
Description=Run Auto Futures V6 MTF scan every 60 seconds

[Timer]
OnBootSec=20s
OnUnitActiveSec=60s
AccuracySec=3s
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable auto-futures-telegram.service
systemctl enable --now auto-futures-scan.timer

echo "INSTALL COMPLETE"
echo "Edit /opt/trading/.env.telegram, then: systemctl enable --now auto-futures-telegram.service"
