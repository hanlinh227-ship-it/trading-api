#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DST=$APP/ops/security
SRC="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_RUNNER; exit 1; }
mkdir -p "$DST"
# Stage only non-secret code. Runner must remain unable to read signer keys/socket.
for spec in \
  "micro-live/micro-live-executor-v192.js:micro-live-executor-v192.js:0644" \
  "v170-root-install-ready-signer.sh:v170-root-install-ready-signer.sh:0750" \
  "v180-root-create-wallet-after-validation.sh:v180-root-create-wallet-after-validation.sh:0750" \
  "v192-root-install-micro-executor.sh:v192-root-install-micro-executor.sh:0750" \
  "v193-root-arm-micro-live.sh:v193-root-arm-micro-live.sh:0750" \
  "v194-root-disarm-micro-live.sh:v194-root-disarm-micro-live.sh:0750" \
  "v181-root-arm-micro-live.sh:v181-root-arm-micro-live-legacy.sh:0640"; do
  IFS=: read -r from to mode <<< "$spec"
  [ -f "$SRC/$from" ] || { echo "MISSING=$from"; exit 1; }
  t="$DST/$to.new-$$"; cat "$SRC/$from" > "$t"; chmod "$mode" "$t"; mv -f "$t" "$DST/$to"
done
if [ -f "$SRC/signer/ready_signer_v3.py" ]; then
  t="$DST/ready_signer.py.new-$$"; cat "$SRC/signer/ready_signer_v3.py" > "$t"; chmod 0755 "$t"; mv -f "$t" "$DST/ready_signer.py"
  python3 "$DST/ready_signer.py" --self-test
fi
node --check "$DST/micro-live-executor-v192.js"
for f in v170-root-install-ready-signer.sh v180-root-create-wallet-after-validation.sh v192-root-install-micro-executor.sh v193-root-arm-micro-live.sh v194-root-disarm-micro-live.sh; do bash -n "$DST/$f"; done
if [ -r /var/lib/meme-alpha-signer/keys ] || [ -x /var/lib/meme-alpha-signer/keys ]; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; fi
if [ -S /run/meme-alpha-signer/signer.sock ] && [ -w /run/meme-alpha-signer/signer.sock ]; then echo FAIL_RUNNER_SOCKET_ACCESS; exit 1; fi
cat > "$DST/FINAL-NEXT-ROOT-STEPS.txt" <<'EOF'
1) bash /opt/meme-alpha/app/ops/security/v170-root-install-ready-signer.sh
2) after empirical validation PASS: bash /opt/meme-alpha/app/ops/security/v180-root-create-wallet-after-validation.sh
3) bash /opt/meme-alpha/app/ops/security/v192-root-install-micro-executor.sh
4) fund ONLY the isolated public address with 0.03-0.10 SOL
5) after >=20 empirical lifecycle + validation PASS + stress PASS: bash /opt/meme-alpha/app/ops/security/v193-root-arm-micro-live.sh
Emergency: bash /opt/meme-alpha/app/ops/security/v194-root-disarm-micro-live.sh
EOF
chmod 0644 "$DST/FINAL-NEXT-ROOT-STEPS.txt"
echo FINAL_LIVE_BUNDLE_STAGED=PASS
echo RUNNER_KEY_ACCESS=DENIED_PASS
echo RUNNER_SOCKET_ACCESS=DENIED_PASS
echo WALLET_CREATED=FALSE
echo LIVE_EXECUTION=FALSE
