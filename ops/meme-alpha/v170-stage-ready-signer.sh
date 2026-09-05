#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DST=$APP/ops/security
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_RUNNER; exit 1; }
mkdir -p "$DST"
install -m 0755 "$SRC_DIR/signer/ready_signer.py" "$DST/ready_signer.py"
install -m 0750 "$SRC_DIR/v170-root-install-ready-signer.sh" "$DST/v170-root-install-ready-signer.sh"
python3 -m py_compile "$DST/ready_signer.py"
python3 "$DST/ready_signer.py" --self-test
bash -n "$DST/v170-root-install-ready-signer.sh"
if [ -r /var/lib/meme-alpha-signer/keys ] || [ -x /var/lib/meme-alpha-signer/keys ]; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; fi
echo READY_SIGNER_STAGED=PASS
echo ROOT_INSTALLER_STAGED=PASS
echo WALLET_CREATED=FALSE
echo LIVE_ENABLE=FALSE
