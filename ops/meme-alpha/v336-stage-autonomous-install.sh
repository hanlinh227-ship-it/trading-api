#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v336-stage"
ROOT="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel)}"
BUILD="$ROOT/ops/meme-alpha/v336-build-autonomous-portfolio.sh"
SRC="$ROOT/ops/meme-alpha/micro-live/micro-live-executor-v336-autonomous.js"
INS="$ROOT/ops/meme-alpha/v336-root-install-autonomous-portfolio.sh"
EXPECTED=608785762d5387b58a2bfb4adead1bf29e7cfe9c489472bf7013442a35ab21d2
bash "$BUILD" >/tmp/v336-build.log
cat /tmp/v336-build.log
[ "$(sha256sum "$SRC"|awk '{print $1}')" = "$EXPECTED" ]
mkdir -p "$STAGE"
cp "$SRC" "$STAGE/micro-live-executor-v336-autonomous.js"
cp "$INS" "$STAGE/install-v336.sh"
chmod 0644 "$STAGE/micro-live-executor-v336-autonomous.js"
chmod 0755 "$STAGE/install-v336.sh"
sha256sum "$STAGE/micro-live-executor-v336-autonomous.js"
stat -c 'STAGE %U:%G %a %n' "$STAGE" "$STAGE/micro-live-executor-v336-autonomous.js" "$STAGE/install-v336.sh"
echo 'ROOT_INSTALL_COMMAND=sudo /opt/meme-alpha/app/runtime-status/v336-stage/install-v336.sh'
echo V336_AUTONOMOUS_STAGE_READY=TRUE
