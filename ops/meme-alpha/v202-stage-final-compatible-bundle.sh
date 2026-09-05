#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SEC=$APP/ops/security
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_RUNNER; exit 1; }

# Restage the complete non-secret final bundle first.
bash "$(cd "$(dirname "$0")" && pwd)/v195-stage-final-live-bundle.sh"

# v2.0 hardened universe reports 1.6.1. Keep root-only future transitions
# fail-closed while accepting only the explicitly audited 1.6 and 1.6.1 schemas.
python3 - <<'PY'
from pathlib import Path
root=Path('/opt/meme-alpha/app/ops/security')
for name in ['v180-root-create-wallet-after-validation.sh','v193-root-arm-micro-live.sh','v181-root-arm-micro-live-legacy.sh']:
 p=root/name
 if not p.exists(): continue
 s=p.read_text(); old="u.get('version')=='1.6'"; new="u.get('version') in ('1.6','1.6.1')"
 if old in s: s=s.replace(old,new)
 elif new not in s: raise SystemExit('UNIVERSE_COMPAT_PATTERN_NOT_FOUND_'+name)
 t=p.with_name(p.name+'.new'); t.write_text(s); t.chmod(p.stat().st_mode & 0o777); t.replace(p)
 print('COMPAT_STAGED='+name)
PY
for f in "$SEC"/v170-root-install-ready-signer.sh "$SEC"/v180-root-create-wallet-after-validation.sh "$SEC"/v192-root-install-micro-executor.sh "$SEC"/v193-root-arm-micro-live.sh "$SEC"/v194-root-disarm-micro-live.sh; do bash -n "$f"; done
python3 "$SEC/ready_signer.py" --self-test
node "$SEC/micro-live-executor-v192.js" --self-test
if [ -r /var/lib/meme-alpha-signer/keys ] || [ -x /var/lib/meme-alpha-signer/keys ]; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; fi
if [ -S /run/meme-alpha-signer/signer.sock ] && [ -w /run/meme-alpha-signer/signer.sock ]; then echo FAIL_RUNNER_SOCKET_ACCESS; exit 1; fi
cat > "$SEC/FINAL-NEXT-ROOT-STEPS.txt" <<'EOF'
Current installed safe state: PAPER remains analysis mode; signer and MICRO executor are installed but locked/disabled.
Only after >=20 empirical PAPER lifecycles + Validation PASS + Stress PASS:
1) bash /opt/meme-alpha/app/ops/security/v180-root-create-wallet-after-validation.sh
2) fund ONLY the returned isolated bot public address with 0.03-0.10 SOL
3) bash /opt/meme-alpha/app/ops/security/v193-root-arm-micro-live.sh
Emergency: bash /opt/meme-alpha/app/ops/security/v194-root-disarm-micro-live.sh
Never fund or expose the main Phantom wallet to the bot.
EOF
chmod 0644 "$SEC/FINAL-NEXT-ROOT-STEPS.txt"
echo V202_FINAL_COMPATIBLE_BUNDLE_STAGED=PASS
echo RUNNER_KEY_ACCESS=DENIED_PASS
echo LIVE_EXECUTION=FALSE
