#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SEC=$APP/ops/security
R=$APP/runtime-status
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_RUNNER; exit 1; }
echo '=== MEME ALPHA FINAL ASSISTANT AUDIT ==='
for f in ready_signer.py v170-root-install-ready-signer.sh v180-root-create-wallet-after-validation.sh micro-live-executor-v192.js v192-root-install-micro-executor.sh v193-root-arm-micro-live.sh v194-root-disarm-micro-live.sh; do
  [ -f "$SEC/$f" ] || { echo "MISSING_STAGED=$f"; exit 1; }
done
python3 "$SEC/ready_signer.py" --self-test
node "$SEC/micro-live-executor-v192.js" --self-test
for f in v170-root-install-ready-signer.sh v180-root-create-wallet-after-validation.sh v192-root-install-micro-executor.sh v193-root-arm-micro-live.sh v194-root-disarm-micro-live.sh; do bash -n "$SEC/$f"; done
[ "$(systemctl show actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service -p User --value)" = github-runner ]
if [ -r /var/lib/meme-alpha-signer/keys ] || [ -x /var/lib/meme-alpha-signer/keys ]; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; fi
if [ -S /run/meme-alpha-signer/signer.sock ] && [ -w /run/meme-alpha-signer/signer.sock ]; then echo FAIL_RUNNER_SOCKET_ACCESS; exit 1; fi
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=(n)=>{try{return JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'))}catch{return null}};
const v=read('validation.json'),s=read('stress-test.json'),u=read('universe.json'),g=read('micro-live-gate.json'),sig=read('signal-snapshot.json');
console.log(`VALIDATION_STATUS=${v?.readinessStatus||'MISSING'}`);
console.log(`COMPLETED_LIFECYCLES=${Number(v?.completedLifecycleTrades||0)}`);
console.log(`STRESS_STATUS=${s?.status||'MISSING'}`);
console.log(`STRESS_FAIL=${Number(s?.fail??-1)}`);
console.log(`UNIVERSE_VERSION=${u?.version||'MISSING'}`);
console.log(`UNKNOWN_ENTRY_ELIGIBLE=${String(u?.unknownEntryEligible)}`);
console.log(`MICRO_GATE_ALLOWED=${String(g?.allowed)}`);
console.log(`MICRO_GATE_REASONS=${(g?.reasons||[]).join(',')}`);
console.log(`SIGNAL_SNAPSHOT=${sig?.version||'MISSING'}`);
NODE
printf 'READY_SIGNER_INSTALLED='; [ -x /opt/meme-alpha-signer/ready_signer.py ] && echo TRUE || echo FALSE
printf 'BOT_WALLET_EXISTS='; [ -f /var/lib/meme-alpha-signer/keys/bot-keypair.json ] && echo TRUE || echo FALSE
printf 'MICRO_EXECUTOR_UNIT_INSTALLED='; [ -f /etc/systemd/system/meme-alpha-micro-live.service ] && echo TRUE || echo FALSE
printf 'MICRO_EXECUTOR_ACTIVE='; systemctl is-active --quiet meme-alpha-micro-live.service 2>/dev/null && echo TRUE || echo FALSE
printf 'EXECUTION_MODE='; cat /etc/meme-alpha/execution-mode 2>/dev/null || echo DISABLED
echo RUNNER_ISOLATION=PASS
echo FINAL_ROOT_BUNDLE_STAGED=PASS
echo ASSISTANT_SIDE_ENGINEERING=COMPLETE
echo V196_FINAL_ASSISTANT_AUDIT_PASS
# post-root-install verification trigger 2026-09-05
