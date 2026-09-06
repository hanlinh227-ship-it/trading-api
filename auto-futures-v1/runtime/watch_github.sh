#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
LOG="$ROOT/auto-futures-v1/logs/github_watch.log"
LOCK="/tmp/auto-futures-update.lock"
BRANCH="auto-futures-v1"
BOT="$ROOT/auto-futures-v1"
MEME_DEPLOY="$BOT/runtime/deploy_meme_alpha_v377.sh"

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
  "$BOT/runtime/update_auto_futures.sh" >> "$LOG" 2>&1
  log "UPDATE FINISHED"
  exit 0
fi

# Isolated meme-alpha deployment hook. It never modifies futures state and it
# returns success while deferred. Its own fail-closed checks require root,
# zero meme positions, offline self-tests, backups, health validation and
# rollback before a production source change can persist.
if [[ -x "$MEME_DEPLOY" ]]; then
  if "$MEME_DEPLOY" >> "$LOG" 2>&1; then
    :
  else
    rc=$?
    log "MEME_ALPHA_DEPLOY_HOOK_FAILED rc=$rc"
  fi
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
  log "NO UPDATE: $LOCAL | UNIFIED HUB HEALTHY"
fi
