#!/usr/bin/env bash
set -Eeuo pipefail
REPO="/opt/trading/trading-api"
WT="/opt/trading/signal-v10-src"
LOCK="/tmp/signal-v10-update.lock"
exec 9>"$LOCK"; flock -n 9 || exit 0
cd "$REPO"
git fetch origin main --quiet
TARGET="$(git rev-parse origin/main)"
if [[ ! -d "$WT/.git" && ! -f "$WT/.git" ]]; then
  rm -rf "$WT"
  git worktree add --detach "$WT" "$TARGET"
fi
cd "$WT"
CURRENT="$(git rev-parse HEAD)"
[[ "$CURRENT" == "$TARGET" ]] && exit 0
git reset --hard "$TARGET"
python3 -m py_compile signal-only-v10/ai_council_worker.py
bash -n signal-only-v10/runtime/install_signal_v10.sh signal-only-v10/runtime/update_signal_v10.sh
systemctl restart signal-v10-council.service
printf '%s SIGNAL_V10_UPDATED %s -> %s\n' "$(date -u -Is)" "$CURRENT" "$TARGET"
