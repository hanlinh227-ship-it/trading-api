#!/usr/bin/env bash
set -euo pipefail
INS=/opt/meme-alpha/app/runtime-status/v331-stage/install-v331.sh
[ -x "$INS" ] || { echo V333_FAIL=INSTALLER_NOT_STAGED; exit 1; }
echo '=== V333 ATTEMPT NARROW-SUDO MULTI POSITION ACTIVATION ==='
if sudo -n "$INS"; then
  echo V333_MULTI_POSITION_ACTIVATION=SUCCESS
else
  rc=$?
  echo "V333_MULTI_POSITION_ACTIVATION=PRIVILEGE_BLOCKED rc=$rc"
  exit "$rc"
fi
