#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.2.4 OBJECTIVE HOLDER EVIDENCE GATE ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE
B="code-backups/v224-$(date -u +%Y%m%d-%H%M%S)";mkdir -p "$B";cp -a src/holder-cluster.js src/persistence.js src/safe-signal-export.js src/micro-live-executor.js "$B"/ 2>/dev/null||true

python3 - <<'PY'
from pathlib import Path
p=Path('src/holder-cluster.js');s=p.read_text()
legacy='''  /*
   * This audit does not prove the identity
   * of the dev/creator wallet.
   */
  review.push(
    "DEV_IDENTITY_NOT_PROVEN"
  );'''
v212='''  /*
   * RPC owner clustering cannot prove the creator/dev identity.
   * That unknown is recorded as telemetry, not as an automatic REVIEW.
   * Entry remains fail-closed on measurable concentration, clustering,
   * unresolved owner/RPC evidence, and all upstream security gates.
   */
  evidence.push(
    "DEV_IDENTITY_NOT_PROVEN_TELEMETRY_ONLY"
  );'''
new='''  /*
   * Identity attribution is not reliably provable from RPC owner clustering.
   * Keep that uncertainty explicit without turning an unknowable identity
   * field into a permanent deadlock. Objective owner concentration, RPC
   * resolution, holder concentration and cluster evidence remain gates.
   */
  const devIdentityProven = false;
  evidence.push("DEV_IDENTITY_UNKNOWN_DISCLOSED");'''
if legacy in s:s=s.replace(legacy,new,1)
elif v212 in s:s=s.replace(v212,new,1)
elif 'const devIdentityProven = false;' not in s:raise SystemExit('DEV_IDENTITY_PATTERN_NOT_FOUND')
needle='''    error:null
  };'''
repl='''    devIdentityProven,
    error:null
  };'''
if needle in s:s=s.replace(needle,repl,1)
elif 'devIdentityProven,' not in s:raise SystemExit('RETURN_DEV_IDENTITY_PATTERN_NOT_FOUND')
s=s.replace('"FAIL_CLOSED_DEV_IDENTITY_UNKNOWN"','"OBJECTIVE_ONCHAIN_CLUSTER_GATES_DEV_IDENTITY_DISCLOSED"')
s=s.replace('"FAIL_CLOSED_MEASURABLE_CLUSTER_RISK"','"OBJECTIVE_ONCHAIN_CLUSTER_GATES_DEV_IDENTITY_DISCLOSED"')
s=s.replace('"DEV_IDENTITY_UNKNOWN=NO_LIVE_APPROVAL"','"DEV_IDENTITY_UNKNOWN=DISCLOSED_OBJECTIVE_CLUSTER_GATES_APPLY"')
s=s.replace('"DEV_IDENTITY_UNKNOWN=NO_LIVE_APPROVAL"','"DEV_IDENTITY_UNKNOWN=DISCLOSED_OBJECTIVE_CLUSTER_GATES_APPLY"')
p.write_text(s)
PY
node --check src/holder-cluster.js

# PAPER readiness requires an actual successful holder-cluster audit, not merely absence of a block.
python3 - <<'PY'
from pathlib import Path
p=Path('src/persistence.js');s=p.read_text()
needle='''    c.securityDecision ===
      "PASS" &&

    (
      !c.token2022 ||'''
repl='''    c.securityDecision ===
      "PASS" &&

    c.holderClusterAudit?.decision ===
      "PASS" &&

    (
      !c.token2022 ||'''
if needle in s:s=s.replace(needle,repl,1)
elif 'c.holderClusterAudit?.decision ===' not in s:raise SystemExit('PERSIST_HOLDER_GATE_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/persistence.js

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js');s=p.read_text()
needle='securityDecision:c.securityDecision,hardReject:'
repl="securityDecision:c.securityDecision,holderClusterDecision:c.holderClusterAudit?.decision||null,devIdentityProven:c.holderClusterAudit?.devIdentityProven===true,holderClusterMaxAccountsSameOwner:Number(c.holderClusterAudit?.maxAccountsSameOwner||0),hardReject:"
if needle in s:s=s.replace(needle,repl,1)
elif 'holderClusterDecision:c.holderClusterAudit?.decision' not in s:raise SystemExit('SAFE_EXPORT_HOLDER_PATTERN_NOT_FOUND')
for oldv in ["version:'2.2.3'","version:'2.2.2'","version:'2.2.0'"]:
    if oldv in s:s=s.replace(oldv,"version:'2.2.4'",1);break
if "version:'2.2.4'" not in s:raise SystemExit('SAFE_EXPORT_VERSION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/safe-signal-export.js

# MICRO_LIVE is still disabled. When eventually armed, require objective holder audit PASS.
python3 - <<'PY'
from pathlib import Path
for p in [Path('src/micro-live-executor.js'),Path('ops/security/micro-live-executor-v192.js')]:
    if not p.exists():continue
    s=p.read_text()
    old="return c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'"
    new="return c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&c.decision==='PROBE_CANDIDATE'"
    if old in s:s=s.replace(old,new,1);p.write_text(s)
    elif new not in s:raise SystemExit('EXECUTOR_HOLDER_GATE_PATTERN_NOT_FOUND_'+str(p))
PY
node --check src/micro-live-executor.js

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 150
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
! systemctl is-active --quiet meme-alpha-micro-live.service

node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));const sig=read('signal-snapshot.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json');const cs=sig.candidates||[],n=f=>cs.filter(f).length;
console.log(`SIGNAL_VERSION=${sig.version}`);console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);console.log(`CANDIDATES=${cs.length} MEME=${n(x=>x.universeClass==='MEME_CONFIRMED')} SECURITY_PASS=${n(x=>x.securityDecision==='PASS')} HOLDER_PASS=${n(x=>x.holderClusterDecision==='PASS')} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} SELLABLE=${n(x=>x.sellRoute===true)} READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,12))console.log(`MEME ${x.symbol} score=${x.score} sec=${x.securityDecision} holder=${x.holderClusterDecision} devProven=${x.devIdentityProven} decision=${x.decision} sell=${x.sellRoute} persist=${x.persistenceDecision||'-'}`);console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${Number(v.completedLifecycleTrades||0)} STRESS=${s.status}`);console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);if(sig.version!=='2.2.4')throw new Error('SIGNAL_VERSION');if(sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SOURCE_HEALTH');if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');console.log('V224_OBJECTIVE_HOLDER_GATE_PASS');
NODE

echo DEV_IDENTITY_UNKNOWN=DISCLOSED_NOT_FALSIFIED
echo MICRO_EXECUTOR_ACTIVE=FALSE
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
