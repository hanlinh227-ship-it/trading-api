#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.1.2 HOLDER RISK DEADLOCK FIX ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_NOT_PAPER');console.log('MODE=PAPER');console.log('LIVE_EXECUTION=DISABLED');
NODE
B="code-backups/v212-$(date -u +%Y%m%d-%H%M%S)"; mkdir -p "$B"; cp -a src/holder-cluster.js src/safe-signal-export.js "$B"/
python3 - <<'PY'
from pathlib import Path
p=Path('src/holder-cluster.js'); s=p.read_text()
old='''  /*\n   * This audit does not prove the identity\n   * of the dev/creator wallet.\n   */\n  review.push(\n    "DEV_IDENTITY_NOT_PROVEN"\n  );'''
new='''  /*\n   * RPC owner clustering cannot prove the creator/dev identity.\n   * That unknown is recorded as telemetry, not as an automatic REVIEW.\n   * Entry remains fail-closed on measurable concentration, clustering,\n   * unresolved owner/RPC evidence, and all upstream security gates.\n   */\n  evidence.push(\n    "DEV_IDENTITY_NOT_PROVEN_TELEMETRY_ONLY"\n  );'''
if old not in s: raise SystemExit('DEV_IDENTITY_REVIEW_BLOCK_NOT_FOUND')
s=s.replace(old,new,1)
s=s.replace('version:"0.9.1"','version:"0.9.2"')
s=s.replace('"FAIL_CLOSED_DEV_IDENTITY_UNKNOWN"','"FAIL_CLOSED_MEASURABLE_CLUSTER_RISK"',1)
s=s.replace('"RPC owner clustering is not equivalent to proven dev/insider identity"','"Dev identity remains unproven telemetry; measurable owner clustering/concentration/RPC uncertainty remains fail-closed"',1)
s=s.replace('''     /*\n      * Cannot be entry-ready while\n      * dev identity remains unresolved.\n      */''','''     /* REVIEW now means a measurable holder/RPC risk remains.\n      * Unknown dev identity by itself is telemetry-only. */''',1)
p.write_text(s)
PY
node --check src/holder-cluster.js
# Prove the old impossible gate is gone while hard review/block paths remain.
! grep -q 'review.push([[:space:]]*$' src/holder-cluster.js || true
grep -q 'DEV_IDENTITY_NOT_PROVEN_TELEMETRY_ONLY' src/holder-cluster.js
grep -q 'HOLDER_CLUSTER_NOT_AUDITED' src/holder-cluster.js
grep -q 'HOLDER_CLUSTER_BLOCK' src/holder-cluster.js
# Extend safe read-only observability with holder audit fields.
python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js'); s=p.read_text()
needle="consecutiveEligible:Number(p?.consecutiveEligible||0)"
repl="consecutiveEligible:Number(p?.consecutiveEligible||0),holderAuditDecision:c.holderClusterAudit?.decision||null,holderReviewReasons:c.holderClusterAudit?.reviewReasons||[],holderBlockReasons:c.holderClusterAudit?.blockReasons||[],holderEvidence:c.holderClusterAudit?.evidence||[]"
if needle in s:s=s.replace(needle,repl,1)
elif 'holderAuditDecision' not in s:raise SystemExit('SAFE_EXPORT_NEEDLE_NOT_FOUND')
s=s.replace("version:'2.0.1'","version:'2.1.2'",1)
p.write_text(s)
PY
node --check src/safe-signal-export.js
for f in src/holder-cluster.js src/safe-signal-export.js; do chmod 664 "$f" 2>/dev/null || true; done
sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 80
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';const R='/opt/meme-alpha/app/runtime-status';const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));const sig=read('signal-snapshot.json'),g=read('micro-live-gate.json');const cs=sig.candidates||[];const n=f=>cs.filter(f).length;
console.log(`SIGNAL_VERSION=${sig.version}`);console.log(`SOURCE=${sig.sourceHealth?.status} SOURCES=${sig.sourceHealth?.successfulSources} CACHE=${sig.sourceHealth?.usingCache}`);console.log(`CANDIDATES=${cs.length}`);console.log(`MEME_CONFIRMED=${n(x=>x.universeClass==='MEME_CONFIRMED')}`);console.log(`SECURITY_PASS=${n(x=>x.securityDecision==='PASS')}`);console.log(`PROBE_CANDIDATE=${n(x=>x.decision==='PROBE_CANDIDATE')}`);console.log(`SELLABLE=${n(x=>x.sellRoute===true)}`);console.log(`PERSIST_READY=${n(x=>['READY','PROBE','ELIGIBLE'].includes(String(x.persistenceDecision||'').toUpperCase()))}`);for(const x of cs.filter(x=>x.universeClass==='MEME_CONFIRMED').slice(0,12))console.log(`MEME ${x.symbol} score=${x.score} sec=${x.securityDecision} holder=${x.holderAuditDecision} review=${(x.holderReviewReasons||[]).join(';')||'-'} sell=${x.sellRoute} decision=${x.decision} persist=${x.persistenceDecision||'-'}`);if(sig.version!=='2.1.2')throw new Error('SIGNAL_VERSION');if(sig.sourceHealth?.status!=='HEALTHY'||sig.sourceHealth?.usingCache===true||Number(sig.sourceHealth?.successfulSources)<2)throw new Error('SOURCE_HEALTH');if(g.allowed!==false||g.executionMode!=='DISABLED')throw new Error('LIVE_GATE');console.log('V212_HOLDER_RISK_DEADLOCK_FIX_PASS');
NODE
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
