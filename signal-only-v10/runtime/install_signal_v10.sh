#!/usr/bin/env bash
set -Eeuo pipefail
REPO="/opt/trading/trading-api"
WT="/opt/trading/signal-v10-src"
ENVFILE="/opt/trading/.env.signal-v10"
cd "$REPO"
git fetch origin main
TARGET="$(git rev-parse origin/main)"
if [[ ! -d "$WT" ]]; then git worktree add --detach "$WT" "$TARGET"; else (cd "$WT" && git reset --hard "$TARGET"); fi
chmod +x "$WT/signal-only-v10/runtime/"*.sh "$WT/signal-only-v10/ai_council_worker.py"
python3 -m py_compile "$WT/signal-only-v10/ai_council_worker.py"

# Derive the existing Cloudflare worker origin from the current Telegram webhook.
set +u
source /opt/trading/.env.telegram 2>/dev/null || true
set -u
ORIGIN="${SIGNAL_V10_ORIGIN:-}"
if [[ -z "$ORIGIN" && -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  ORIGIN="$(python3 - <<'PY'
import json,os,urllib.request,urllib.parse
k=os.environ.get('TELEGRAM_BOT_TOKEN','').strip()
try:
 d=json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{k}/getWebhookInfo',timeout=15));u=str((d.get('result') or {}).get('url') or '')
 p=urllib.parse.urlparse(u);print(f'{p.scheme}://{p.netloc}' if p.scheme and p.netloc else '')
except Exception: print('')
PY
)"
fi
if [[ -z "$ORIGIN" ]]; then echo "FAIL: cannot derive SIGNAL_V10_ORIGIN from existing Telegram webhook" >&2; exit 20; fi

cat > "$ENVFILE" <<EOF
SIGNAL_V10_ORIGIN="$ORIGIN"
SIGNAL_V10_POLL_SECONDS="7"
SIGNAL_V10_BATCH_LIMIT="3"
SIGNAL_V10_CLAUDE_TIMEOUT="48"
SIGNAL_V10_DEEPSEEK_TIMEOUT="35"
SIGNAL_V10_CODEX_TIMEOUT="48"
SIGNAL_V10_CLAUDE_MODEL="sonnet"
SIGNAL_V10_DEEPSEEK_MODEL="deepseek-chat"
SIGNAL_V10_CODEX_MODEL="gpt-5.6-sol"
EOF
chmod 600 "$ENVFILE"

cat > /etc/systemd/system/signal-v10-council.service <<'EOF'
[Unit]
Description=Signal Only V10 Dedicated Three-AI Council
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=root
WorkingDirectory=/opt/trading/signal-v10-src
EnvironmentFile=-/opt/trading/.env.telegram
EnvironmentFile=-/opt/trading/.env.ai
EnvironmentFile=-/opt/trading/.env.signal-v10
ExecStart=/usr/bin/python3 /opt/trading/signal-v10-src/signal-only-v10/ai_council_worker.py
Restart=always
RestartSec=5
Nice=5
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/signal-v10-update.service <<'EOF'
[Unit]
Description=Signal Only V10 GitHub Main Updater
After=network-online.target
[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/trading/trading-api
ExecStart=/opt/trading/signal-v10-src/signal-only-v10/runtime/update_signal_v10.sh
TimeoutStartSec=180
EOF
cat > /etc/systemd/system/signal-v10-update.timer <<'EOF'
[Unit]
Description=Signal Only V10 Update Timer
[Timer]
OnBootSec=90s
OnUnitInactiveSec=5min
AccuracySec=10s
Persistent=false
Unit=signal-v10-update.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now signal-v10-council.service signal-v10-update.timer
systemctl restart signal-v10-council.service

echo "========================================"
echo "SIGNAL ONLY V10 INSTALLED"
echo "SOURCE=$WT @ $TARGET"
echo "ORIGIN=$ORIGIN"
echo "COUNCIL=$(systemctl is-active signal-v10-council.service || true)"
echo "UPDATER=$(systemctl is-active signal-v10-update.timer || true)"
echo "BINANCE_AUTO_SERVICES=UNTOUCHED"
echo "========================================"
