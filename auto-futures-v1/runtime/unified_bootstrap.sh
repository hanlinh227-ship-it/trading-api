#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
BOT="$ROOT/auto-futures-v1"
BRANCH="auto-futures-v1"

echo "========================================"
echo "AUTO FUTURES UNIFIED BOOTSTRAP"
echo "GitHub -> VPS -> Telegram -> Binance"
echo "========================================"

cd "$ROOT"

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

mkdir -p "$BOT/state" "$BOT/logs" "$BOT/backups"
chmod +x "$BOT/run_pipeline.sh" "$BOT/runtime/"*.sh 2>/dev/null || true

# Telegram env template: secrets stay local on VPS only.
if [[ ! -f /opt/trading/.env.telegram ]]; then
  cat > /opt/trading/.env.telegram <<'EOF'
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
TELEGRAM_ALLOWED_USER_ID=""
EOF
  chmod 600 /opt/trading/.env.telegram
  echo "TELEGRAM_ENV_CREATED=1"
else
  chmod 600 /opt/trading/.env.telegram
  echo "TELEGRAM_ENV_EXISTS=1"
fi

# Install/update Telegram approval hub + 60s scalp timer.
"$BOT/runtime/install_telegram_approval.sh"

# GitHub auto-update service/timer.
cat > /etc/systemd/system/auto-futures-update.service <<'EOF'
[Unit]
Description=Auto Futures GitHub Safe Updater
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/trading/trading-api
ExecStart=/opt/trading/trading-api/auto-futures-v1/runtime/watch_github.sh
TimeoutStartSec=900
EOF

cat > /etc/systemd/system/auto-futures-update.timer <<'EOF'
[Unit]
Description=Check Auto Futures GitHub Updates Every 5 Minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=10s
Persistent=true
Unit=auto-futures-update.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now auto-futures-update.timer
systemctl enable --now auto-futures-scan.timer
systemctl enable --now auto-futures-position.service

# Syntax validation.
python3 -m py_compile \
  "$BOT/paper_trader.py" \
  "$BOT/ai/common.py" \
  "$BOT/ai/claude_trader.py" \
  "$BOT/ai/deepseek_trader.py" \
  "$BOT/ai/codex_trader.py" \
  "$BOT/ai/consensus.py" \
  "$BOT/risk/risk_engine.py" \
  "$BOT/execution/execution_guard.py" \
  "$BOT/execution/live_executor.py" \
  "$BOT/execution/telegram_hub.py" \
  "$BOT/position/position_manager.py"

echo "PYTHON_SYNTAX=PASS"

# Keep real execution locked until Telegram credentials are valid and user arms it.
if [[ -f /opt/trading/.env.binance ]]; then
  grep -q '^BINANCE_LIVE_TRADING=' /opt/trading/.env.binance \
    && sed -i 's/^BINANCE_LIVE_TRADING=.*/BINANCE_LIVE_TRADING="false"/' /opt/trading/.env.binance \
    || echo 'BINANCE_LIVE_TRADING="false"' >> /opt/trading/.env.binance
  grep -q '^BINANCE_LIVE_ARMED=' /opt/trading/.env.binance \
    && sed -i 's/^BINANCE_LIVE_ARMED=.*/BINANCE_LIVE_ARMED="false"/' /opt/trading/.env.binance \
    || echo 'BINANCE_LIVE_ARMED="false"' >> /opt/trading/.env.binance
  chmod 600 /opt/trading/.env.binance
fi

# Start Telegram hub only when credentials are present.
set +u
source /opt/trading/.env.telegram 2>/dev/null || true
set -u
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" && -n "${TELEGRAM_ALLOWED_USER_ID:-}" ]]; then
  systemctl enable --now auto-futures-telegram.service
  TELEGRAM_STATUS="$(systemctl is-active auto-futures-telegram.service || true)"
else
  systemctl stop auto-futures-telegram.service 2>/dev/null || true
  TELEGRAM_STATUS="NEEDS_CREDENTIALS"
fi

UPDATE_STATUS="$(systemctl is-active auto-futures-update.timer || true)"
SCAN_STATUS="$(systemctl is-active auto-futures-scan.timer || true)"
POSITION_STATUS="$(systemctl is-active auto-futures-position.service || true)"

echo
echo "========================================"
echo "UNIFIED SYSTEM STATUS"
echo "========================================"
echo "BRANCH=$BRANCH"
echo "UPDATE_TIMER=$UPDATE_STATUS"
echo "SCAN_TIMER=$SCAN_STATUS"
echo "POSITION_MANAGER=$POSITION_STATUS"
echo "TELEGRAM_HUB=$TELEGRAM_STATUS"
if [[ -f /opt/trading/.env.binance ]]; then
  grep -E '^BINANCE_(LIVE_TRADING|LIVE_ARMED)=' /opt/trading/.env.binance || true
fi

echo "========================================"
if [[ "$TELEGRAM_STATUS" == "NEEDS_CREDENTIALS" ]]; then
  echo "NEXT=fill /opt/trading/.env.telegram then rerun this script"
else
  echo "NEXT=validate Telegram signal/confirmation flow before arming live"
fi
