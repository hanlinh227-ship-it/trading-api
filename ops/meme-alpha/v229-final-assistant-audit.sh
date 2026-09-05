#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
R=$APP/runtime-status
cd "$APP"

echo '=== MEME ALPHA v2.2.9 FINAL ASSISTANT-SIDE AUDIT ==='
[ "$(id -un)" = github-runner ] || { echo FAIL_RUNNER_USER; exit 1; }
echo RUNNER_USER=github-runner

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER')throw new Error('MODE_NOT_PAPER');
console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE

systemctl is-active --quiet meme-alpha-paper.service
echo PAPER_SERVICE_ACTIVE=PASS
[ "$(systemctl is-enabled meme-alpha-paper.service 2>/dev/null)" = enabled ]
echo PAPER_SERVICE_ENABLED=PASS
! systemctl is-active --quiet meme-alpha-micro-live.service
echo MICRO_EXECUTOR_INACTIVE=PASS
[ "$(systemctl is-enabled meme-alpha-micro-live.service 2>/dev/null || true)" != enabled ]
echo MICRO_EXECUTOR_DISABLED=PASS

RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ]
echo ROOT_RUNNER_REMOVED=PASS
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; else echo RUNNER_KEY_ACCESS=DENIED_PASS; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo FAIL_RUNNER_SIGNER_SOCKET; exit 1; else echo RUNNER_SIGNER_SOCKET=DENIED_PASS; fi

# Static fail-closed invariants.
grep -q 'JUPITER_MIN_INTERVAL_MS = 2200' src/scanner.js
grep -q 'SELLABILITY_TEMPORARILY_UNAVAILABLE' src/scanner.js
grep -q 'c.universeClass ===' src/persistence.js
grep -q '"MEME_CONFIRMED"' src/persistence.js
grep -Fq 'c.holderClusterAudit?.decision ===' src/persistence.js
grep -Fq 'c.sellRoute === true' src/persistence.js
grep -Fq "c.sellPriceImpactPct??c.sellImpactPct??c.priceImpactPct" src/micro-live-executor.js
grep -Fq "c.holderClusterDecision==='PASS'" src/micro-live-executor.js
grep -q 'QUOTE_BACKOFF_FULL_GAP_SEC=30' run-paper.sh
grep -q 'TURBO_FULL_GAP_SEC=12' run-paper.sh
echo STATIC_FAIL_CLOSED_INVARIANTS=PASS

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));
const sig=read('signal-snapshot.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json'),u=read('universe.json');
const cs=sig.candidates||[],n=f=>cs.filter(f).length;
console.log(`SIGNAL_VERSION=${sig.version}`);
console.log(`SOURCE_STATUS=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} FAILED=${sig.sourceHealth?.failedSources} CACHE=${sig.sourceHealth?.usingCache}`);
console.log(`CANDIDATES=${cs.length} MEME_CONFIRMED=${n(x=>x.universeClass==='MEME_CONFIRMED')} SECURITY_PASS=${n(x=>x.securityDecision==='PASS')} HOLDER_PASS=${n(x=>x.holderClusterDecision==='PASS')} SELLABLE=${n(x=>x.sellRoute===true)} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);
console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${Number(v.completedLifecycleTrades||0)} MIN=${v.minCompletedLifecycles||20}`);
console.log(`STRESS=${s.status} STRESS_FAIL=${s.fail}`);
console.log(`UNIVERSE_VERSION=${u.version} UNKNOWN_ENTRY_ELIGIBLE=${u.unknownEntryEligible}`);
console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
if(sig.version!=='2.2.7')throw new Error('SIGNAL_NOT_LATEST');
if(sig.sourceHealth?.status!=='HEALTHY'||Number(sig.sourceHealth?.successfulSources)<2||sig.sourceHealth?.usingCache===true)throw new Error('SOURCE_HEALTH');
if(u.unknownEntryEligible!==false)throw new Error('UNKNOWN_UNIVERSE_ENTRY_ALLOWED');
if(v.readinessStatus==='FAIL')throw new Error('VALIDATION_FAILED');
if(s.status==='FAIL'||Number(s.fail)>0)throw new Error('STRESS_FAILED');
if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('MICRO_LIVE_SHOULD_BE_LOCKED');
console.log('RUNTIME_FAIL_CLOSED_INVARIANTS=PASS');
NODE

echo NO_WALLET_ACTION_PERFORMED=TRUE
echo NO_NETWORK_EXECUTION_PERFORMED=TRUE
echo V229_FINAL_ASSISTANT_AUDIT_PASS
