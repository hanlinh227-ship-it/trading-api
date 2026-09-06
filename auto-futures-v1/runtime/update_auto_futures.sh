#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/opt/trading/trading-api";BOT="$ROOT/auto-futures-v1";BRANCH="auto-futures-v1";BACKUP_ROOT="/opt/trading/auto-futures-backups";LOG="$BOT/logs/auto_update.log";LOCK="/tmp/auto-futures-deploy.lock";TS="$(date +%Y%m%d_%H%M%S)";BACKUP="$BACKUP_ROOT/release_$TS";BACKUP_READY=0
mkdir -p "$BACKUP_ROOT" "$BOT/logs";log(){ echo "$(date -u -Is) $*" | tee -a "$LOG"; };cd "$ROOT";exec 8>"$LOCK";if ! flock -n 8;then log "DEPLOY_SKIP reason=DEPLOY_LOCK_BUSY";exit 0;fi
LIVE_TRADING="false";LIVE_ARMED="false";if [[ -f /opt/trading/.env.binance ]];then set -a;source /opt/trading/.env.binance;set +a;LIVE_TRADING="${BINANCE_LIVE_TRADING:-false}";LIVE_ARMED="${BINANCE_LIVE_ARMED:-false}";fi

# Meme Alpha v3.82 reconciliation is intentionally independent from the Binance/Auto-Futures
# deployment gate. A live/pending Binance position must never prevent the root-owned Meme Alpha
# ARM state from being reconciled.
MEME_RECON="$BOT/runtime/deploy_meme_alpha_v382_reconcile.sh"
run_meme_reconcile(){
  local phase="$1" out rc
  [[ -f "$MEME_RECON" ]] || { log "MEME_RECONCILE_${phase} rc=0 result=SCRIPT_MISSING"; return 0; }
  set +e
  out="$(/bin/bash "$MEME_RECON" 2>&1)"; rc=$?
  set -e
  log "MEME_RECONCILE_${phase} rc=$rc result=$(echo "$out" | tail -n 1)"
  return 0
}
run_meme_reconcile EARLY

pending_count(){ python3 - <<'PY'
import json
from pathlib import Path
p=Path('/opt/trading/trading-api/auto-futures-v1/state/pending_trades.json')
try:d=json.loads(p.read_text());print(sum(1 for x in d.get('items',[]) if x.get('status') in {'PENDING','CONFIRMING'}))
except Exception:print(0)
PY
}
live_count(){ python3 - <<'PY'
import json
from pathlib import Path
p=Path('/opt/trading/trading-api/auto-futures-v1/state/live_preflight.json')
try:print(int(json.loads(p.read_text()).get('live_open_positions',0) or 0))
except Exception:print(0)
PY
}
if [[ -f "$BOT/execution/live_preflight.py" && -f /opt/trading/.env.binance ]];then python3 "$BOT/execution/live_preflight.py" >/tmp/auto_futures_preupdate_preflight.out 2>&1 || true;fi
OPEN_NOW="$(live_count)";PENDING_NOW="$(pending_count)";if [[ "$OPEN_NOW" -gt 0 || "$PENDING_NOW" -gt 0 ]];then log "DEPLOY_DEFER open_live=$OPEN_NOW pending=$PENDING_NOW";exit 0;fi
log "========================================";log "PRODUCTION UPDATE START live=$LIVE_TRADING armed=$LIVE_ARMED";log "========================================";mkdir -p "$BACKUP";cp -a "$BOT" "$BACKUP/auto-futures-v1";BACKUP_READY=1;log "BACKUP PASS: $BACKUP"
rollback(){ rc=$?;trap - ERR;log "UPDATE FAILED rc=$rc";if [[ "$BACKUP_READY" -eq 1 && -d "$BACKUP/auto-futures-v1" ]];then log "ROLLBACK START";systemctl stop auto-futures-scan.timer auto-futures-scan.service auto-futures-hub-bridge.service auto-futures-position.service signal-v10-council.service 2>/dev/null || true;rm -rf "$ROOT/auto-futures-v1.failed.$TS" 2>/dev/null || true;[[ -d "$BOT" ]]&&mv "$BOT" "$ROOT/auto-futures-v1.failed.$TS";cp -a "$BACKUP/auto-futures-v1" "$BOT";systemctl daemon-reload || true;systemctl start auto-futures-position.service auto-futures-hub-bridge.service auto-futures-scan.timer signal-v10-council.service 2>/dev/null || true;log "ROLLBACK COMPLETE";fi;exit "$rc";};trap rollback ERR
systemctl stop auto-futures-scan.timer auto-futures-scan.service 2>/dev/null || true;pkill -f '/auto-futures-v1/ai/(claude|deepseek|codex)_trader.py' 2>/dev/null || true
git fetch origin "$BRANCH";git checkout -f "$BRANCH";git reset --hard "origin/$BRANCH";log "GITHUB SOURCE SYNC PASS: $(git rev-parse HEAD)"
# Critical second pass: EARLY ran the pre-sync script. Rebind to the freshly pulled
# reconcile code and execute it immediately, before the slower Auto-Futures bootstrap.
MEME_RECON="$BOT/runtime/deploy_meme_alpha_v382_reconcile.sh"
run_meme_reconcile POST_SYNC

# v3.83 breadth-only scanner deployment.
MEME_V383="$BOT/runtime/deploy_meme_alpha_v383_scanner_breadth.sh"
if [[ -f "$MEME_V383" ]]; then
  set +e
  V383_OUT="$(/bin/bash "$MEME_V383" 2>&1)"; V383_RC=$?
  set -e
  log "MEME_V383_SCANNER rc=$V383_RC result=$(echo "$V383_OUT" | tail -n 1)"
fi

# v3.84 adaptive opportunity queue: keep top-quality candidates every cycle and
# rotate a bounded tail so every preliminary candidate gets repeated opportunities
# without saturating Jupiter/Dexscreener. Hard safety remains fail-closed.
MEME_V384="$BOT/runtime/deploy_meme_alpha_v384_adaptive_breadth.sh"
if [[ -f "$MEME_V384" ]]; then
  set +e
  V384_OUT="$(/bin/bash "$MEME_V384" 2>&1)"; V384_RC=$?
  set -e
  log "MEME_V384_ADAPTIVE rc=$V384_RC result=$(echo "$V384_OUT" | tail -n 1)"
fi

FILES=( auto-futures-v1/paper_trader.py auto-futures-v1/ai/common.py auto-futures-v1/ai/ai_budget_governor.py auto-futures-v1/ai/ai_coordination.py auto-futures-v1/ai/claude_trader.py auto-futures-v1/ai/deepseek_trader.py auto-futures-v1/ai/codex_trader.py auto-futures-v1/ai/consensus.py auto-futures-v1/risk/risk_engine.py auto-futures-v1/execution/execution_guard.py auto-futures-v1/execution/live_preflight.py auto-futures-v1/execution/approval_queue.py auto-futures-v1/execution/live_executor.py auto-futures-v1/execution/hub_control_bridge.py auto-futures-v1/research/market_context_monitor.py auto-futures-v1/research/signal_quality_guard.py auto-futures-v1/research/reliability_learner.py auto-futures-v1/position/ai_position_guardian.py auto-futures-v1/position/position_manager.py signal-only-v10/ai_council_worker.py )
for f in "${FILES[@]}";do [[ -f "$ROOT/$f" ]]||{ log "FAIL missing=$f";exit 30;};done
python3 -m py_compile "${FILES[@]}";bash -n "$BOT/run_pipeline.sh" "$BOT/runtime/scan_loop.sh" "$BOT/runtime/watch_github.sh" "$BOT/runtime/update_auto_futures.sh" "$BOT/runtime/unified_bootstrap.sh" "$ROOT/signal-only-v10/runtime/install_signal_v10.sh";log "STATIC VALIDATION PASS"
BOOTSTRAP_SKIP_GIT=1 "$BOT/runtime/unified_bootstrap.sh" >/tmp/auto_futures_bootstrap.out 2>&1;log "AUTO FUTURES SERVICE RECONCILE PASS"
chmod 700 "$ROOT/signal-only-v10/runtime/install_signal_v10.sh";"$ROOT/signal-only-v10/runtime/install_signal_v10.sh" >/tmp/signal_v10_install.out 2>&1;log "SIGNAL V10 COUNCIL RECONCILE PASS"
if [[ -f /opt/trading/.env.binance ]];then set -a;source /opt/trading/.env.binance;set +a;[[ "${BINANCE_LIVE_TRADING:-false}" == "$LIVE_TRADING" ]];[[ "${BINANCE_LIVE_ARMED:-false}" == "$LIVE_ARMED" ]];fi
sleep 2;POSITION="$(systemctl is-active auto-futures-position.service || true)";SCAN="$(systemctl is-active auto-futures-scan.timer || true)";UPDATE="$(systemctl is-active auto-futures-update.timer || true)";HUB="$(systemctl is-active auto-futures-hub-bridge.service || true)";SIGV10="$(systemctl is-active signal-v10-council.service || true)";[[ "$POSITION" == "active" ]];[[ "$SCAN" == "active" ]];[[ "$UPDATE" == "active" ]];[[ "$SIGV10" == "active" ]];log "HEALTH position=$POSITION scan=$SCAN update=$UPDATE hub=$HUB signal_v10=$SIGV10"
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'release_*' -mtime +14 -exec rm -rf {} + 2>/dev/null || true;log "PRODUCTION UPDATE COMPLETE live=$LIVE_TRADING armed=$LIVE_ARMED signal_v10=$SIGV10";trap - ERR;exit 0
