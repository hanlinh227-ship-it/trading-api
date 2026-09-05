#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
R=$APP/runtime-status
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
cd "$APP"
echo '=== MEME ALPHA FINAL BUILD PREFLIGHT ==='
FAIL=0
pass(){ echo "PASS $*"; }
fail(){ echo "FAIL $*"; FAIL=$((FAIL+1)); }

ru=$(systemctl show "$RUNNER_UNIT" -p User --value || true)
[ "$ru" = github-runner ] && pass "RUNNER_NON_ROOT user=$ru" || fail "RUNNER_USER=$ru"
[ "$(id -un)" = github-runner ] && pass "WORKFLOW_USER=github-runner" || fail "WORKFLOW_USER=$(id -un)"
systemctl is-active --quiet meme-alpha-paper.service && pass PAPER_SERVICE_ACTIVE || fail PAPER_SERVICE_INACTIVE
systemctl is-active --quiet meme-alpha-signer.service && pass SIGNER_SERVICE_ACTIVE || fail SIGNER_SERVICE_INACTIVE
if sudo -n /usr/bin/id >/dev/null 2>&1; then fail ARBITRARY_SUDO_AVAILABLE; else pass ARBITRARY_SUDO_DENIED; fi
if [ -r /var/lib/meme-alpha-signer/keys ] || [ -x /var/lib/meme-alpha-signer/keys ]; then fail RUNNER_SIGNER_KEYS_ACCESSIBLE; else pass RUNNER_SIGNER_KEYS_DENIED; fi
if [ -S /run/meme-alpha-signer/signer.sock ] && [ -w /run/meme-alpha-signer/signer.sock ]; then fail RUNNER_SIGNER_SOCKET_WRITABLE; else pass RUNNER_SIGNER_SOCKET_DENIED; fi

for f in ready_signer.py v170-root-install-ready-signer.sh v180-root-create-wallet-after-validation.sh v181-root-arm-micro-live.sh v191-root-install-micro-executor.sh v192-root-emergency-disarm.sh micro-live-executor.js; do
  [ -f "$APP/ops/security/$f" ] && pass "STAGED_$f" || fail "MISSING_$f"
done
python3 -m py_compile "$APP/ops/security/ready_signer.py" && pass READY_SIGNER_COMPILES || fail READY_SIGNER_COMPILE
python3 "$APP/ops/security/ready_signer.py" --self-test >/tmp/ma-signer-selftest.$$ 2>&1 && pass READY_SIGNER_SELFTEST || { cat /tmp/ma-signer-selftest.$$; fail READY_SIGNER_SELFTEST; }
rm -f /tmp/ma-signer-selftest.$$
node --check "$APP/ops/security/micro-live-executor.js" && pass MICRO_EXECUTOR_COMPILES || fail MICRO_EXECUTOR_COMPILE
node "$APP/ops/security/micro-live-executor.js" --self-test >/tmp/ma-exec-selftest.$$ 2>&1 && pass MICRO_EXECUTOR_SELFTEST || { cat /tmp/ma-exec-selftest.$$; fail MICRO_EXECUTOR_SELFTEST; }
rm -f /tmp/ma-exec-selftest.$$

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));
const runtime=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
const u=read('universe.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json'),sig=read('signal-snapshot.json');
console.log(`RUNTIME_MODE=${runtime.mode}`);
console.log(`UNIVERSE_VERSION=${u.version} UNKNOWN_ENTRY_ELIGIBLE=${u.unknownEntryEligible}`);
console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${v.completedLifecycleTrades}`);
console.log(`STRESS=${s.status} FAIL=${s.fail}`);
console.log(`GATE_ALLOWED=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
console.log(`SIGNAL_VERSION=${sig.version} CANDIDATES=${(sig.candidates||[]).length}`);
if(runtime.mode!=='PAPER') process.exit(11);
if(u.unknownEntryEligible!==false) process.exit(12);
if(g.allowed!==false||g.executionMode!=='DISABLED') process.exit(13);
NODE
rc=$?; [ "$rc" -eq 0 ] && pass FAIL_CLOSED_RUNTIME_STATE || fail "FAIL_CLOSED_RUNTIME_STATE rc=$rc"

KEYCOUNT=$(find /var/lib/meme-alpha-signer/keys -maxdepth 1 -type f 2>/dev/null | wc -l)
[ "$KEYCOUNT" -eq 0 ] && pass "NO_WALLET_CREATED count=$KEYCOUNT" || fail "UNEXPECTED_WALLET_FILES=$KEYCOUNT"
for f in /etc/meme-alpha/execution-mode /etc/meme-alpha/micro-live-armed /etc/meme-alpha/signer-enabled; do [ ! -e "$f" ] && pass "DISARMED_$(basename "$f")" || fail "ARM_FILE_PRESENT=$f"; done

# Informational status; incomplete empirical validation is not a build failure.
node --input-type=module - <<'NODE'
import fs from 'node:fs';const v=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/validation.json'));const s=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/stress-test.json'));console.log(`EMPIRICAL_REMAINING=${Math.max(0,20-Number(v.completedLifecycleTrades||0))}`);console.log(`EMPIRICAL_VALIDATION_STATUS=${v.readinessStatus}`);console.log(`EMPIRICAL_STRESS_STATUS=${s.status}`);
NODE

echo "BUILD_PREFLIGHT_FAILURES=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
echo 'FINAL_BUILD_PREFLIGHT=PASS'
