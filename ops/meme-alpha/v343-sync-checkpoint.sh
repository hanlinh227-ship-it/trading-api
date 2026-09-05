#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SRC="$ROOT/ops/meme-alpha/CHECKPOINT.md"
DST="/opt/meme-alpha/app/runtime-status/MEME_ALPHA_CHECKPOINT.md"
[ -f "$SRC" ] || { echo CHECKPOINT_SOURCE_MISSING; exit 1; }
install -m 0664 "$SRC" "$DST"
echo CHECKPOINT_SYNCED_TO=$DST
sha256sum "$SRC" "$DST"
echo V343_CHECKPOINT_SYNC_ACTIVE=TRUE
