#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
BOT="$ROOT/auto-futures-v1"
BRANCH="auto-futures-v1"

echo "========================================"
echo "AUTO FUTURES UNIFIED BOOTSTRAP V8"
echo "GitHub -> Existing Cloudflare Hub -> VPS -> Binance"
echo "========================================"

cd "$ROOT"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

mkdir -p "$BOT/state" "$BOT/logs" "$BOT/backups"
chmod +x "$BOT/run_pipeline.sh" "$BOT/runtime/"*.sh 2>/dev/null || true

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

systemctl disable --now auto-futures-telegram.service >/dev/null 2>&1 || true

cat > /etc/systemd/system/auto-futures-hub-bridge.service <<'EOF'
[Unit]
Description=Auto Futures V8 Existing Hub Control Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trading/trading-api
EnvironmentFile=-/opt/trading/.env.ai
EnvironmentFile=-/opt/trading/.env.binance
EnvironmentFile=-/opt/trading/.env.telegram
ExecStart=/usr/bin/python3 /opt/trading/trading-api/auto-futures-v1/execution/hub_control_bridge.py
Restart=always
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/auto-futures-scan.timer <<'EOF'
[Unit]
Description=Run Auto Futures V8 MTF scan every 60 seconds

[Timer]
OnBootSec=20s
OnUnitActiveSec=60s
AccuracySec=3s
Persistent=true
Unit=auto-futures-scan.service

[Install]
WantedBy=timers.target
EOF

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

python3 -m py_compile \
  "$BOT/paper_trader.py" \
  "$BOT/ai/common.py" \
  "$BOT/ai/claude_trader.py" \
  "$BOT/ai/deepseek_trader.py" \
  "$BOT/ai/codex_trader.py" \
  "$BOT/ai/consensus.py" \
  "$BOT/risk/risk_engine.py" \
  "$BOT/execution/execution_guard.py" \
  "$BOT/execution/live_preflight.py" \
  "$BOT/execution/approval_queue.py" \
  "$BOT/execution/live_executor.py" \
  "$BOT/execution/hub_control_bridge.py" \
  "$BOT/research/market_context_monitor.py" \
  "$BOT/research/reliability_learner.py" \
  "$BOT/position/ai_position_guardian.py" \
  "$BOT/position/position_manager.py"

echo "PYTHON_SYNTAX=PASS"

if [[ -f /opt/trading/.env.binance ]]; then
  grep -q '^BINANCE_LIVE_TRADING=' /opt/trading/.env.binance && sed -i 's/^BINANCE_LIVE_TRADING=.*/BINANCE_LIVE_TRADING="false"/' /opt/trading/.env.binance || echo 'BINANCE_LIVE_TRADING="false"' >> /opt/trading/.env.binance
  grep -q '^BINANCE_LIVE_ARMED=' /opt/trading/.env.binance && sed -i 's/^BINANCE_LIVE_ARMED=.*/BINANCE_LIVE_ARMED="false"/' /opt/trading/.env.binance || echo 'BINANCE_LIVE_ARMED="false"' >> /opt/trading/.env.binance
  chmod 600 /opt/trading/.env.binance
fi

set +u
source /opt/trading/.env.telegram 2>/dev/null || true
set -u
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  systemctl enable --now auto-futures-hub-bridge.service
  systemctl restart auto-futures-hub-bridge.service
  HUB_STATUS="$(systemctl is-active auto-futures-hub-bridge.service || true)"
else
  systemctl stop auto-futures-hub-bridge.service 2>/dev/null || true
  HUB_STATUS="NEEDS_EXISTING_HUB_CREDENTIALS"
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
echo "BINANCE_HUB_BRIDGE=$HUB_STATUS"
echo "LIVE_PREFLIGHT=fail_closed"
echo "EXECUTION_IDEMPOTENCY=entry_client_order_id"
echo "INCIDENT_LOCK=enabled"
echo "RELIABILITY_COUNCIL=event_gated_6h_cache"
echo "MARKET_CONTEXT=20s_cached"
echo "AI_TOKEN_MODE=event_gated_90s_cache"
echo "POSITION_GUARDIAN=HOLD_REDUCE_EXIT"
echo "DUPLICATE_TELEGRAM_HUB=disabled"
if [[ -f /opt/trading/.env.binance ]]; then grep -E '^BINANCE_(LIVE_TRADING|LIVE_ARMED)=' /opt/trading/.env.binance || true; fi
echo "========================================"
if [[ "$HUB_STATUS" == "NEEDS_EXISTING_HUB_CREDENTIALS" ]]; then echo "NEXT=reuse the existing Hub TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in /opt/trading/.env.telegram"; else echo "NEXT=run V8 pipeline and inspect live_preflight/reliability before arming live"; fi
