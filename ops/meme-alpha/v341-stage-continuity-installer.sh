#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v341-stage"
SRC="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/v341-root-install-continuity-scan.sh"
mkdir -p "$STAGE"
cp "$SRC" "$STAGE/install-v341.sh"
chmod 0755 "$STAGE/install-v341.sh"
stat -c 'STAGE %U:%G %a %n' "$STAGE" "$STAGE/install-v341.sh"
echo ROOT_INSTALL_COMMAND='sudo /opt/meme-alpha/app/runtime-status/v341-stage/install-v341.sh'
echo V341_CONTINUITY_STAGE_READY=TRUE
