#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
LOG="$ROOT/auto-futures-v1/logs/github_watch.log"
LOCK="/tmp/auto-futures-update.lock"
BRANCH="auto-futures-v1"
BOT="$ROOT/auto-futures-v1"
MEME_DEPLOY_V377="$BOT/runtime/deploy_meme_alpha_v377.sh"
MEME_DEPLOY_V378="$BOT/runtime/deploy_meme_alpha_v378.sh"
MEME_RECON_V382="$BOT/runtime/deploy_meme_alpha_v382_reconcile.sh"

mkdir -p "$(dirname "$LOG")"
log(){ echo "$(date -u -Is) $*" >> "$LOG"; }

cd "$ROOT"
exec 9>"$LOCK"
if ! flock -n 9; then log "SKIP: another update is running"; exit 0; fi

git fetch origin "$BRANCH" >/dev/null 2>&1
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL" != "$REMOTE" ]]; then
  log "NEW COMMIT: local=$LOCAL remote=$REMOTE"
  log "STARTING SAFE UPDATE"
  set +e
  "$BOT/runtime/update_auto_futures.sh" >> "$LOG" 2>&1
  UPDATE_RC=$?
  set -e
  if [[ "$UPDATE_RC" -eq 0 ]]; then
    log "UPDATE FINISHED"
  else
    log "UPDATE FAILED rc=$UPDATE_RC; continuing isolated meme reconcile"
  fi
fi

# Legacy compatibility hooks. They remain fail-closed and must never downgrade
# the currently installed executor.
for MEME_DEPLOY in "$MEME_DEPLOY_V377" "$MEME_DEPLOY_V378"; do
  if [[ -x "$MEME_DEPLOY" ]]; then
    set +e
    "$MEME_DEPLOY" >> "$LOG" 2>&1
    rc=$?
    set -e
    if [[ "$rc" -ne 0 ]]; then
      log "MEME_ALPHA_DEPLOY_HOOK_FAILED name=$(basename "$MEME_DEPLOY") rc=$rc"
    fi
  fi
done

# Current v3.82 ARM self-heal lane. Run on EVERY watcher tick, even with no Git
# delta, so loss/drift of /etc/meme-alpha/micro-live-armed is repaired quickly.
# Invoke explicitly through /bin/bash instead of relying on the executable bit;
# this gives the root watcher a second recovery path if file mode drift occurred.
# The reconcile script itself remains fail-closed: ARMED=NO always wins; unknown
# states are rejected; signer/source/risk must be healthy before writing ARMED=YES.
if [[ -f "$MEME_RECON_V382" ]]; then
  set +e
  /bin/bash "$MEME_RECON_V382" >> "$LOG" 2>&1
  rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    log "MEME_ALPHA_RECONCILE_FAILED name=$(basename "$MEME_RECON_V382") rc=$rc"
  fi
else
  log "MEME_ALPHA_RECONCILE_MISSING name=$(basename "$MEME_RECON_V382")"
fi

# Self-heal the one-Hub architecture after an older updater has pulled the new release.
NEEDS_RECONCILE=0
systemctl cat auto-futures-hub-bridge.service >/dev/null 2>&1 || NEEDS_RECONCILE=1
if systemctl is-active --quiet auto-futures-telegram.service 2>/dev/null; then NEEDS_RECONCILE=1; fi
if [[ "$NEEDS_RECONCILE" -eq 1 ]]; then
  log "NO GIT UPDATE, BUT UNIFIED HUB RECONCILE REQUIRED"
  "$BOT/runtime/unified_bootstrap.sh" >> "$LOG" 2>&1
  log "UNIFIED HUB RECONCILE FINISHED"
else
  LOCAL="$(git rev-parse HEAD 2>/dev/null || true)"
  log "WATCH COMPLETE: ${LOCAL:-unknown} | UNIFIED HUB HEALTHY"
fi
