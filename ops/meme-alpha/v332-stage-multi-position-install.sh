#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v331-stage"
SRC="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/micro-live/micro-live-executor-v331-multi.js"
INS="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/v331-root-install-multi-position.sh"
EXPECTED=e80fe028b1db808a1b2a892efcb9087fd2330a79184dcb7b75b5feb79cbd7d90
mkdir -p "$STAGE"
[ "$(sha256sum "$SRC"|awk '{print $1}')" = "$EXPECTED" ]
/usr/bin/node --check "$SRC"
/usr/bin/node "$SRC" --self-test | grep -q 'MICRO_EXECUTOR_V331_MULTI_SELF_TEST=PASS'
cp "$SRC" "$STAGE/micro-live-executor-v331-multi.js"
cp "$INS" "$STAGE/install-v331.sh"
chmod 0644 "$STAGE/micro-live-executor-v331-multi.js"
chmod 0755 "$STAGE/install-v331.sh"
sha256sum "$STAGE/micro-live-executor-v331-multi.js"
stat -c 'STAGE %U:%G %a %n' "$STAGE" "$STAGE/micro-live-executor-v331-multi.js" "$STAGE/install-v331.sh"
echo 'ROOT_INSTALL_COMMAND=sudo /opt/meme-alpha/app/runtime-status/v331-stage/install-v331.sh'
echo V332_MULTI_POSITION_STAGE_READY=TRUE
