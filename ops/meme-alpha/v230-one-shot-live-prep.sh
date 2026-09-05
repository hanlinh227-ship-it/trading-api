#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
R=$APP/runtime-status
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service

cd "$APP"
echo '=== MEME ALPHA v2.3.0 ONE-SHOT LIVE PREP ==='

[ "$(id -un)" = github-runner ] || { echo FAIL_RUNNER_USER; exit 1; }
[ -f config/runtime.json ] || { echo FAIL_RUNTIME_CONFIG_MISSING; exit 1; }
[ -f "$R/signal-snapshot.json" ] || { echo FAIL_SIGNAL_SNAPSHOT_MISSING; exit 1; }

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

# Hard safety lock: this workflow prepares for live but can never turn live on.
systemctl is-active --quiet meme-alpha-paper.service
[ "$(systemctl is-enabled meme-alpha-paper.service 2>/dev/null)" = enabled ]
! systemctl is-active --quiet meme-alpha-micro-live.service
[ "$(systemctl is-enabled meme-alpha-micro-live.service 2>/dev/null || true)" != enabled ]
echo PAPER_SERVICE=ACTIVE_ENABLED
echo MICRO_LIVE_SERVICE=INACTIVE_DISABLED

# Runner isolation must already be complete before any future key exists.
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ]
echo RUNNER_ISOLATION=PASS

# Signer isolation must exist and remain LOCKED. The runner must not be able to reach key material/socket.
systemctl is-active --quiet meme-alpha-signer.service
[ "$(systemctl show meme-alpha-signer.service -p User --value)" = meme-alpha-signer ]
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then
  echo FAIL_RUNNER_KEY_ACCESS
  exit 1
fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then
  echo FAIL_RUNNER_SIGNER_SOCKET_ACCESS
  exit 1
fi
echo SIGNER_ISOLATION=PASS_LOCKED_FROM_RUNNER

# Installed strategy/execution invariants accumulated from previous hardening phases.
grep -q 'JUPITER_MIN_INTERVAL_MS = 2200' src/scanner.js
grep -q 'SELLABILITY_TEMPORARILY_UNAVAILABLE' src/scanner.js
grep -q 'MEME_CONFIRMED' src/persistence.js
grep -Fq 'c.sellRoute === true' src/persistence.js
grep -Fq 'c.holderClusterAudit?.decision ===' src/persistence.js
grep -Fq "c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct" src/micro-live-executor.js
grep -Fq "c.holderClusterDecision==='PASS'" src/micro-live-executor.js
grep -q 'QUOTE_BACKOFF_FULL_GAP_SEC=30' run-paper.sh
grep -q 'TURBO_FULL_GAP_SEC=12' run-paper.sh
echo INTEGRATED_FAIL_CLOSED_LOGIC=PASS

# Refresh only when the exported signal is stale. No extra network pressure when current data is already fresh.
SIG="$R/signal-snapshot.json"
AGE=$(( $(date +%s) - $(stat -c %Y "$SIG") ))
echo "SIGNAL_FILE_AGE_SEC=$AGE"
if [ "$AGE" -gt 180 ]; then
  echo SIGNAL_REFRESH=RESTART_PAPER
  BEFORE=$(stat -c %Y "$SIG")
  sudo -n /bin/systemctl restart meme-alpha-paper.service
  ok=0
  for _ in $(seq 1 30); do
    sleep 8
    NOW=$(stat -c %Y "$SIG" 2>/dev/null || echo 0)
    if [ "$NOW" -gt "$BEFORE" ]; then
      if node --input-type=module - <<'NODE'
import fs from 'node:fs';
const s=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/signal-snapshot.json','utf8'));
if(s.version!=='2.2.7') process.exit(2);
if(s.sourceHealth?.status!=='HEALTHY') process.exit(3);
if(Number(s.sourceHealth?.successfulSources)<2) process.exit(4);
if(s.sourceHealth?.usingCache===true) process.exit(5);
NODE
      then ok=1; break; fi
    fi
  done
  [ "$ok" -eq 1 ] || { echo FAIL_FRESH_HEALTHY_SIGNAL_TIMEOUT; exit 1; }
else
  echo SIGNAL_REFRESH=NOT_NEEDED
fi

# Run the consolidated final audit from the checked-out repository against the installed runtime.
bash "$REPO_ROOT/ops/meme-alpha/v229-final-assistant-audit.sh"

# One final machine-readable readiness decision. Technical prep may pass while statistical evidence continues accumulating.
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));
const sig=read('signal-snapshot.json');
const v=read('validation.json');
const s=read('stress-test.json');
const g=read('micro-live-gate.json');
const u=read('universe.json');
const cs=sig.candidates||[];
const count=f=>cs.filter(f).length;
const completed=Number(v.completedLifecycleTrades||0);
const min=Number(v.minCompletedLifecycles||20);
const stressFail=Number(s.fail||0);
const evidenceReady=completed>=min && v.readinessStatus!=='FAIL' && s.status==='PASS' && stressFail===0;
const technicalReady=
  sig.version==='2.2.7' &&
  sig.sourceHealth?.status==='HEALTHY' &&
  Number(sig.sourceHealth?.successfulSources)>=2 &&
  sig.sourceHealth?.usingCache!==true &&
  u.unknownEntryEligible===false &&
  g.allowed===false &&
  g.executionMode==='DISABLED';
if(!technicalReady) throw new Error('TECHNICAL_PREP_NOT_READY');
console.log(`SIGNAL_VERSION=${sig.version}`);
console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAILED=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`CANDIDATES=${cs.length} MEME_CONFIRMED=${count(x=>x.universeClass==='MEME_CONFIRMED')} SECURITY_PASS=${count(x=>x.securityDecision==='PASS')} HOLDER_PASS=${count(x=>x.holderClusterDecision==='PASS')} SELLABLE=${count(x=>x.sellRoute===true)} PROBE=${count(x=>x.decision==='PROBE_CANDIDATE')} READY=${count(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);
console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${completed} MIN=${min}`);
console.log(`STRESS=${s.status} STRESS_FAIL=${stressFail}`);
console.log('TECHNICAL_LIVE_PREP=PASS');
console.log(`STATISTICAL_EVIDENCE_READY=${evidenceReady}`);
console.log(`LIVE_PREP_STAGE=${evidenceReady?'READY_FOR_CONTROLLED_MICRO_LIVE_ACTIVATION':'TECHNICALLY_READY_PAPER_EVIDENCE_ACCUMULATING'}`);
console.log('MICRO_LIVE_REMAINS_LOCKED=TRUE');
console.log('WALLET_ACTION_PERFORMED=FALSE');
console.log('NETWORK_EXECUTION_PERFORMED=FALSE');
NODE

echo V230_ONE_SHOT_LIVE_PREP_PASS
