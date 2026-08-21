#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
BOT="$ROOT/auto-futures-v1"
BRANCH="auto-futures-v1"
BACKUP_ROOT="/opt/trading/auto-futures-backups"
LOG="$BOT/logs/auto_update.log"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP="$BACKUP_ROOT/release_$TS"
BACKUP_READY=0

log(){ echo "$(date -u -Is) $*" | tee -a "$LOG"; }
rollback(){
  rc=$?; trap - ERR; log "UPDATE FAILED rc=$rc"
  if [[ "$BACKUP_READY" -eq 1 && -d "$BACKUP/auto-futures-v1" ]]; then
    log "ROLLBACK START"
    systemctl stop auto-futures-hub-bridge.service auto-futures-position.service auto-futures-scan.timer 2>/dev/null || true
    rm -rf "$ROOT/auto-futures-v1.failed.$TS" 2>/dev/null || true
    [[ -d "$BOT" ]] && mv "$BOT" "$ROOT/auto-futures-v1.failed.$TS"
    cp -a "$BACKUP/auto-futures-v1" "$BOT"
    systemctl daemon-reload || true
    systemctl restart auto-futures-position.service auto-futures-scan.timer 2>/dev/null || true
    log "ROLLBACK COMPLETE"
  fi
  exit "$rc"
}
trap rollback ERR

mkdir -p "$BACKUP_ROOT" "$BOT/logs"
cd "$ROOT"
log "========================================"
log "AUTO FUTURES UNIFIED UPDATE START"
log "========================================"

mkdir -p "$BACKUP"
cp -a "$BOT" "$BACKUP/auto-futures-v1"
BACKUP_READY=1
log "BACKUP PASS: $BACKUP"

# Every software deployment disarms real execution. Re-arming is a separate user action.
if [[ -f /opt/trading/.env.binance ]]; then
  grep -q '^BINANCE_LIVE_TRADING=' /opt/trading/.env.binance && sed -i 's/^BINANCE_LIVE_TRADING=.*/BINANCE_LIVE_TRADING="false"/' /opt/trading/.env.binance || echo 'BINANCE_LIVE_TRADING="false"' >> /opt/trading/.env.binance
  grep -q '^BINANCE_LIVE_ARMED=' /opt/trading/.env.binance && sed -i 's/^BINANCE_LIVE_ARMED=.*/BINANCE_LIVE_ARMED="false"/' /opt/trading/.env.binance || echo 'BINANCE_LIVE_ARMED="false"' >> /opt/trading/.env.binance
  chmod 600 /opt/trading/.env.binance
fi
log "LIVE SAFETY LOCK PASS"

git fetch origin "$BRANCH"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || git checkout "$BRANCH"
if [[ -n "$(git status --porcelain)" ]]; then
  log "WARNING: repository contains local changes"
  git status --short | tee -a "$LOG"
fi
git pull --ff-only origin "$BRANCH"
log "GITHUB UPDATE PASS"

[[ -f /opt/trading/.env.ai ]] && { set -a; source /opt/trading/.env.ai; set +a; }
[[ -f /opt/trading/.env.binance ]] && { set -a; source /opt/trading/.env.binance; set +a; }
[[ -f /opt/trading/.env.telegram ]] && { set -a; source /opt/trading/.env.telegram; set +a; }
[[ "${BINANCE_LIVE_TRADING:-false}" == "false" ]]
[[ "${BINANCE_LIVE_ARMED:-false}" == "false" ]]

FILES=(
 auto-futures-v1/paper_trader.py
 auto-futures-v1/ai/common.py
 auto-futures-v1/ai/claude_trader.py
 auto-futures-v1/ai/deepseek_trader.py
 auto-futures-v1/ai/codex_trader.py
 auto-futures-v1/ai/consensus.py
 auto-futures-v1/risk/risk_engine.py
 auto-futures-v1/execution/execution_guard.py
 auto-futures-v1/execution/approval_queue.py
 auto-futures-v1/execution/live_executor.py
 auto-futures-v1/execution/hub_control_bridge.py
 auto-futures-v1/position/position_manager.py
)
for f in "${FILES[@]}"; do [[ -f "$ROOT/$f" ]] || { log "FAIL missing $f"; exit 30; }; done
python3 -m py_compile "${FILES[@]}"
log "PYTHON SYNTAX PASS"

log "AI TEST START"
timeout 120 claude --model sonnet -p 'Return exactly this JSON and nothing else: {"status":"OK"}' >/tmp/auto_futures_claude.out 2>/tmp/auto_futures_claude.err
grep -q '"status":"OK"' /tmp/auto_futures_claude.out
log "CLAUDE PASS"

python3 auto-futures-v1/ai/deepseek_trader.py >/tmp/auto_futures_deepseek.out 2>/tmp/auto_futures_deepseek.err
grep -q '"status"' /tmp/auto_futures_deepseek.out
grep -q 'OK' /tmp/auto_futures_deepseek.out
log "DEEPSEEK PASS"

timeout 180 codex exec 'Return exactly this JSON and nothing else: {"status":"OK"}' >/tmp/auto_futures_codex.out 2>/tmp/auto_futures_codex.err
grep -q '"status":"OK"' /tmp/auto_futures_codex.out
log "CODEX PASS"

timeout 700 "$BOT/run_pipeline.sh" >/tmp/auto_futures_pipeline.out 2>&1
grep -q 'PIPELINE COMPLETE' /tmp/auto_futures_pipeline.out
log "PIPELINE PASS"

# Install/reconcile all systemd units, including the existing-Hub bridge.
chmod +x "$BOT/runtime/unified_bootstrap.sh" "$BOT/runtime/watch_github.sh" "$BOT/runtime/update_auto_futures.sh"
"$BOT/runtime/unified_bootstrap.sh" >/tmp/auto_futures_bootstrap.out 2>&1
log "UNIFIED BOOTSTRAP PASS"

sleep 3
POSITION="$(systemctl is-active auto-futures-position.service || true)"
SCAN="$(systemctl is-active auto-futures-scan.timer || true)"
UPDATE="$(systemctl is-active auto-futures-update.timer || true)"
HUB="$(systemctl is-active auto-futures-hub-bridge.service || true)"
[[ "$POSITION" == "active" ]]
[[ "$SCAN" == "active" ]]
[[ "$UPDATE" == "active" ]]
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then [[ "$HUB" == "active" ]]; fi
log "POSITION=$POSITION SCAN=$SCAN UPDATE=$UPDATE HUB_BRIDGE=$HUB"
log "HEALTH CHECK PASS"

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'release_*' -mtime +14 -exec rm -rf {} + 2>/dev/null || true
log "========================================"
log "AUTO UPDATE COMPLETE"
log "EXISTING_HUB_UNIFIED=true"
log "DUPLICATE_TELEGRAM_HUB=false"
log "LIVE_TRADING=false"
log "LIVE_ARMED=false"
log "========================================"
trap - ERR
exit 0
