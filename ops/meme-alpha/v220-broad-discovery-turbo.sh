#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== MEME ALPHA v2.2.0 BROAD DISCOVERY + ADAPTIVE TURBO ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

B="code-backups/v220-$(date -u +%Y%m%d-%H%M%S)"; mkdir -p "$B"; cp -a src/scanner.js src/safe-signal-export.js run-paper.sh "$B"/

python3 - <<'PY'
from pathlib import Path
p=Path('src/scanner.js'); s=p.read_text()
old='const baseDeep = preliminary.slice(0, 20);'
new='const baseDeep = preliminary.slice(0, 30);'
if old in s: s=s.replace(old,new,1)
elif new not in s: raise SystemExit('BASE_DEEP_PATTERN_NOT_FOUND')
old2='''  })\n  .slice(0, 6);\nconst deep = [...baseDeep, ...extraMeme];'''
new2='''  })\n  .slice(0, 10);\nconst deep = [...baseDeep, ...extraMeme];'''
if old2 in s: s=s.replace(old2,new2,1)
elif new2 not in s: raise SystemExit('EXTRA_MEME_PATTERN_NOT_FOUND')
s=s.replace('// v2.0: keep the best 20, then add at most 6 high-signal meme/launchpad candidates.','// v2.2: keep the best 30, then add at most 10 high-signal meme/launchpad candidates.',1)
p.write_text(s)
PY
node --check src/scanner.js

python3 - <<'PY'
from pathlib import Path
p=Path('run-paper.sh'); s=p.read_text()
if 'TURBO_FULL_GAP_SEC=12' not in s:
    if 'HEALTHY_FULL_GAP_SEC=15' not in s: raise SystemExit('HEALTHY_GAP_PATTERN_NOT_FOUND')
    s=s.replace('HEALTHY_FULL_GAP_SEC=15','TURBO_FULL_GAP_SEC=12\nHEALTHY_FULL_GAP_SEC=15',1)
old="""  const ok=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;\n  console.log(ok?'HEALTHY':'DEGRADED');"""
new="""  const base=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;\n  const turbo=base && Number(h.successfulSources)>=4 && Number(h.failedSources||0)===0;\n  console.log(turbo?'TURBO':(base?'HEALTHY':'DEGRADED'));"""
if old in s: s=s.replace(old,new,1)
elif "console.log(turbo?'TURBO':(base?'HEALTHY':'DEGRADED'));" not in s: raise SystemExit('SOURCE_PROFILE_PATTERN_NOT_FOUND')
old2="""  if [ \"$PROFILE\" = \"HEALTHY\" ]; then\n    GAP=\"$HEALTHY_FULL_GAP_SEC\"\n  else\n    GAP=\"$DEGRADED_FULL_GAP_SEC\"\n  fi"""
new2="""  if [ \"$PROFILE\" = \"TURBO\" ]; then\n    GAP=\"$TURBO_FULL_GAP_SEC\"\n  elif [ \"$PROFILE\" = \"HEALTHY\" ]; then\n    GAP=\"$HEALTHY_FULL_GAP_SEC\"\n  else\n    GAP=\"$DEGRADED_FULL_GAP_SEC\"\n  fi"""
if old2 in s: s=s.replace(old2,new2,1)
elif 'GAP="$TURBO_FULL_GAP_SEC"' not in s: raise SystemExit('GAP_SELECT_PATTERN_NOT_FOUND')
p.write_text(s)
PY
bash -n run-paper.sh

python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js'); s=p.read_text()
if "version:'2.2.2'" not in s:
    for old in ["version:'2.1.6'","version:'2.1.4'","version:'2.1.2'","version:'2.0.1'"]:
        if old in s:
            s=s.replace(old,"version:'2.2.0'",1); break
    if "version:'2.2.0'" not in s: raise SystemExit('SAFE_SIGNAL_VERSION_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/safe-signal-export.js

sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 175
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null

# The isolated GitHub runner intentionally cannot read the private PAPER data directory.
# Use the sanitized runtime-status export for verification instead.
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const R='/opt/meme-alpha/app/runtime-status';
const read=n=>JSON.parse(fs.readFileSync(`${R}/${n}`,'utf8'));
const sig=read('signal-snapshot.json'),v=read('validation.json'),s=read('stress-test.json'),g=read('micro-live-gate.json');
const h=sig.sourceHealth||{};
const cs=sig.candidates||[], n=f=>cs.filter(f).length;
console.log(`SIGNAL_VERSION=${sig.version}`);
console.log(`SOURCE=${h.status} SOURCES=${h.successfulSources} FAIL=${h.failedSources} CACHE=${h.usingCache}`);
console.log(`CANDIDATES=${cs.length} MEME_CONFIRMED=${n(x=>x.universeClass==='MEME_CONFIRMED')} SECURITY_PASS=${n(x=>x.securityDecision==='PASS')} PROBE=${n(x=>x.decision==='PROBE_CANDIDATE')} SELLABLE=${n(x=>x.sellRoute===true)} PAPER_READY=${n(x=>x.persistenceDecision==='PAPER_ENTRY_READY')}`);
console.log(`VALIDATION=${v.readinessStatus} COMPLETED=${Number(v.completedLifecycleTrades||0)}`);
console.log(`STRESS=${s.status} FAIL=${s.fail}`);
console.log(`MICRO_GATE=${g.allowed} EXECUTION_MODE=${g.executionMode}`);
if(!['2.2.0','2.2.2'].includes(sig.version)) throw new Error('SIGNAL_VERSION');
if(h.status!=='HEALTHY'||Number(h.successfulSources)<2||h.usingCache===true) throw new Error('SOURCE_HEALTH');
if(g.allowed!==false||g.executionMode!=='DISABLED') throw new Error('LIVE_GATE');
console.log('V220_BROAD_DISCOVERY_TURBO_PASS');
NODE

grep -E 'TURBO_FULL_GAP_SEC|HEALTHY_FULL_GAP_SEC|DEGRADED_FULL_GAP_SEC' run-paper.sh | head -n 8 || true
echo LIVE_EXECUTION=FALSE
echo "BACKUP=$B"
