#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${BYBIT_BRIDGE_DIR:-/opt/bybit-btc-bridge}
PY=${PYTHON:-python3}
sudo mkdir -p "$APP_DIR"
sudo cp bybit_live_bridge.py "$APP_DIR/bybit_live_bridge.py"
sudo cp bybit_public_proxy.py "$APP_DIR/bybit_public_proxy.py"
sudo cp bybit_public_bridge.py "$APP_DIR/bybit_public_bridge.py"
sudo "$PY" -m pip install --upgrade websocket-client
cat <<'UNIT' | sudo tee /etc/systemd/system/bybit-btc-bridge.service >/dev/null
[Unit]
Description=Bybit live API, public research and microstructure bridge
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=/opt/bybit-btc-bridge
EnvironmentFile=-/etc/bybit-btc-bridge.env
ExecStart=/usr/bin/python3 /opt/bybit-btc-bridge/bybit_public_bridge.py
Restart=always
RestartSec=2
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now bybit-btc-bridge.service
sudo systemctl restart bybit-btc-bridge.service
sudo systemctl --no-pager --full status bybit-btc-bridge.service || true
