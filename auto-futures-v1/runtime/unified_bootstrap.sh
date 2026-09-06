#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/opt/trading/trading-api";BOT="$ROOT/auto-futures-v1";BRANCH="auto-futures-v1";SKIP_GIT="${BOOTSTRAP_SKIP_GIT:-0}"
echo "========================================";echo "AUTO FUTURES PRODUCTION BOOTSTRAP V10";echo "GitHub source-of-truth -> Cloudflare Hub -> VPS -> Binance";echo "========================================"
cd "$ROOT"
if [[ "$SKIP_GIT" != "1" ]]; then git fetch origin "$BRANCH";git checkout -f "$BRANCH";git reset --hard "origin/$BRANCH";fi
mkdir -p "$BOT/state" "$BOT/logs" "$BOT/backups";chmod +x "$BOT/run_pipeline.sh" "$BOT/runtime/"*.sh 2>/dev/null || true
if [[ ! -f /opt/trading/.env.telegram ]]; then cat > /opt/trading/.env.telegram <<'EOF'
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
TELEGRAM_ALLOWED_USER_ID=""
EOF
fi
chmod 600 /opt/trading/.env.telegram
touch /opt/trading/.env.ai
add_ai_default(){ grep -q "^$1=" /opt/trading/.env.ai || echo "$1=$2" >> /opt/trading/.env.ai; }
add_ai_default CLAUDE_BUDGET_WINDOW_HOURS '"5"';add_ai_default CLAUDE_MAX_CALLS_5H '"24"';add_ai_default CLAUDE_RESERVE_CALLS_5H '"6"';add_ai_default CLAUDE_REVIEW_TIMEOUT_SECONDS '"48"'
add_ai_default CODEX_MAX_CALLS_5H '"40"';add_ai_default DEEPSEEK_DAILY_BUDGET_USD '"1.00"';add_ai_default DEEPSEEK_MONTHLY_BUDGET_USD '"15.00"';add_ai_default DEEPSEEK_INPUT_USD_PER_M_TOKENS '"0.28"';add_ai_default DEEPSEEK_OUTPUT_USD_PER_M_TOKENS '"0.42"'
add_ai_default AI_REVIEW_TIMEOUT_SECONDS '"60"';add_ai_default AI_COUNCIL_LOCK_WAIT_SECONDS '"20"';add_ai_default AUTO_FUTURES_SCAN_MAX_RUNTIME_SECONDS '"240"'
chmod 600 /opt/trading/.env.ai
if [[ -f /opt/trading/.env.binance ]]; then grep -q '^BINANCE_LIVE_TRADING=' /opt/trading/.env.binance || echo 'BINANCE_LIVE_TRADING="false"' >> /opt/trading/.env.binance;grep -q '^BINANCE_LIVE_ARMED=' /opt/trading/.env.binance || echo 'BINANCE_LIVE_ARMED="false"' >> /opt/trading/.env.binance;chmod 600 /opt/trading/.env.binance;fi
systemctl disable --now auto-futures-telegram.service >/dev/null 2>&1 || true
cat > /etc/systemd/system/auto-futures-scan.service <<'EOF'
[Unit]
Description=Auto Futures Production Singleton Scanner
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/trading/trading-api
EnvironmentFile=-/opt/trading/.env.ai
EnvironmentFile=-/opt/trading/.env.binance
EnvironmentFile=-/opt/trading/.env.telegram
ExecStart=/opt/trading/trading-api/auto-futures-v1/runtime/scan_loop.sh
TimeoutStartSec=300
Nice=5
EOF
cat > /etc/systemd/system/auto-futures-scan.timer <<'EOF'
[Unit]
Description=Auto Futures Production Scan Scheduler
[Timer]
OnBootSec=20s
OnUnitInactiveSec=45s
AccuracySec=3s
Persistent=false
Unit=auto-futures-scan.service
[Install]
WantedBy=timers.target
EOF
cat > /etc/systemd/system/auto-futures-hub-bridge.service <<'EOF'
[Unit]
Description=Auto Futures Existing Cloudflare Hub Control Bridge
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
cat > /etc/systemd/system/auto-futures-update.service <<'EOF'
[Unit]
Description=Auto Futures GitHub Production Updater
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/trading/trading-api
ExecStart=/opt/trading/trading-api/auto-futures-v1/runtime/watch_github.sh
TimeoutStartSec=300
EOF
cat > /etc/systemd/system/auto-futures-update.timer <<'EOF'
[Unit]
Description=Check Auto Futures GitHub Updates Every 5 Minutes
[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
AccuracySec=10s
Persistent=false
Unit=auto-futures-update.service
[Install]
WantedBy=timers.target
EOF
FILES=( "$BOT/paper_trader.py" "$BOT/ai/common.py" "$BOT/ai/ai_budget_governor.py" "$BOT/ai/ai_coordination.py" "$BOT/ai/claude_trader.py" "$BOT/ai/deepseek_trader.py" "$BOT/ai/codex_trader.py" "$BOT/ai/consensus.py" "$BOT/risk/risk_engine.py" "$BOT/execution/execution_guard.py" "$BOT/execution/live_preflight.py" "$BOT/execution/approval_queue.py" "$BOT/execution/live_executor.py" "$BOT/execution/hub_control_bridge.py" "$BOT/research/market_context_monitor.py" "$BOT/research/signal_quality_guard.py" "$BOT/research/reliability_learner.py" "$BOT/position/ai_position_guardian.py" "$BOT/position/position_manager.py" )
python3 -m py_compile "${FILES[@]}";bash -n "$BOT/run_pipeline.sh" "$BOT/runtime/scan_loop.sh" "$BOT/runtime/watch_github.sh" "$BOT/runtime/update_auto_futures.sh";echo "STATIC_VALIDATION=PASS"
systemctl daemon-reload;systemctl enable --now auto-futures-update.timer;systemctl enable --now auto-futures-scan.timer;systemctl enable --now auto-futures-position.service
set +u;source /opt/trading/.env.telegram 2>/dev/null || true;source /opt/trading/.env.ai 2>/dev/null || true;set -u
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then systemctl enable --now auto-futures-hub-bridge.service;systemctl restart auto-futures-hub-bridge.service;HUB_STATUS="$(systemctl is-active auto-futures-hub-bridge.service || true)";else systemctl stop auto-futures-hub-bridge.service 2>/dev/null || true;HUB_STATUS="NEEDS_EXISTING_HUB_CREDENTIALS";fi
UPDATE_STATUS="$(systemctl is-active auto-futures-update.timer || true)";SCAN_STATUS="$(systemctl is-active auto-futures-scan.timer || true)";POSITION_STATUS="$(systemctl is-active auto-futures-position.service || true)"
echo;echo "========================================";echo "PRODUCTION SYSTEM STATUS";echo "========================================";echo "BRANCH=$BRANCH";echo "GITHUB_SOURCE_OF_TRUTH=true";echo "CLOUDFLARE_HUB=existing_only";echo "SIGNAL_QUALITY_GUARD=V10";echo "SCANNER_FEATURE_SCHEMA_NORMALIZED=true";echo "AI_COUNCIL_SINGLE_FLIGHT=true";echo "AI_PROVIDER_CIRCUIT_BREAKER=true";echo "AI_SHARED_DECISION_CONTRACT=true";echo "CLAUDE_PROMPT_CACHE=API_ONLY_WHEN_CONFIGURED";echo "LIVE_SIZING_SOURCE=BINANCE_AVAILABLE_BALANCE";echo "UPDATE_TIMER=$UPDATE_STATUS";echo "SCAN_TIMER=$SCAN_STATUS";echo "POSITION_MANAGER=$POSITION_STATUS";echo "BINANCE_HUB_BRIDGE=$HUB_STATUS";echo "MAX_LIVE_POSITIONS=5";echo "MARGIN_MODE=ISOLATED_ONLY"
if [[ -f /opt/trading/.env.binance ]]; then grep -E '^BINANCE_(LIVE_TRADING|LIVE_ARMED)=' /opt/trading/.env.binance || true;fi
echo "========================================"
