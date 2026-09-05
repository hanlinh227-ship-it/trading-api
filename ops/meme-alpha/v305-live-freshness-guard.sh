#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LAUNCHER="$APP/run-paper.sh"
GATE="$APP/runtime-status/micro-live-gate.json"
SIG="$APP/runtime-status/signal-snapshot.json"
SERVICE=meme-alpha-paper.service
cd "$APP"

echo '=== V305 R2 LIVE FRESHNESS GUARD ==='
[ -r "$LAUNCHER" ] && [ -w "$LAUNCHER" ] || { echo 'LAUNCHER_NOT_WRITABLE'; exit 2; }
[ -r "$GATE" ] && [ -w "$GATE" ] || { echo 'GATE_NOT_WRITABLE'; exit 3; }

backup="$APP/runtime-status/run-paper-v305-$(date -u +%Y%m%dT%H%M%SZ).sh.bak"
cp -p "$LAUNCHER" "$backup"

if grep -q 'V305_LIVE_FRESHNESS_GUARD' "$LAUNCHER"; then
  echo 'GUARD_ALREADY_PRESENT=TRUE'
else
  tmp=$(mktemp)
  python3 - "$LAUNCHER" > "$tmp" <<'PY_PATCH'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
marker="FAILURE_BACKOFF_SEC=30\n"
if s.count(marker)!=1:
    raise SystemExit('cadence marker mismatch')
guard=r'''
# V305_LIVE_FRESHNESS_GUARD
LIVE_SIGNAL_MAX_AGE_SEC=6
close_entry_gate() {
  local reason="${1:-ENTRY_GATE_GUARD}"
  /usr/bin/node - "$reason" <<'NODE_GUARD' 2>/dev/null || true
const fs=require('fs');
const p='/opt/meme-alpha/app/runtime-status/micro-live-gate.json', reason=process.argv[2]||'ENTRY_GATE_GUARD';
try {
  const x=JSON.parse(fs.readFileSync(p,'utf8'));
  x.allowed=false;
  const rs=Array.isArray(x.reasons)?x.reasons.filter(r=>!String(r).startsWith('FAST_GUARD_')):[];
  if(!rs.includes(reason))rs.push(reason);
  x.reasons=rs;
  x.fastGuard={active:true,reason,updatedAt:new Date().toISOString()};
  const t=p+'.guard.tmp';fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}
} catch {}
NODE_GUARD
}
enforce_entry_freshness() {
  /usr/bin/node - "$LIVE_SIGNAL_MAX_AGE_SEC" <<'NODE_FRESH' 2>/dev/null || true
const fs=require('fs');
const gate='/opt/meme-alpha/app/runtime-status/micro-live-gate.json', sig='/opt/meme-alpha/app/runtime-status/signal-snapshot.json', max=Number(process.argv[2]||6);
try {
  const g=JSON.parse(fs.readFileSync(gate,'utf8')), s=JSON.parse(fs.readFileSync(sig,'utf8'));
  const ms=Date.parse(s.timestamp||s.updatedAt||s.generatedAt||0), age=Number.isFinite(ms)?(Date.now()-ms)/1000:Infinity;
  if(age>max || age<0){
    g.allowed=false;
    const rs=Array.isArray(g.reasons)?g.reasons.filter(r=>!String(r).startsWith('FAST_GUARD_')):[];
    rs.push('FAST_GUARD_SIGNAL_STALE');g.reasons=[...new Set(rs)];
    g.fastGuard={active:true,reason:'FAST_GUARD_SIGNAL_STALE',signalAgeSec:Number.isFinite(age)?Number(age.toFixed(3)):null,maxAgeSec:max,updatedAt:new Date().toISOString()};
    const t=gate+'.guard.tmp';fs.writeFileSync(t,JSON.stringify(g,null,2));fs.renameSync(t,gate);try{fs.chmodSync(gate,0o664)}catch{}
  }
} catch {}
NODE_FRESH
}
'''
s=s.replace(marker,marker+guard+'\n')
cycle='  /usr/bin/npm run cycle5\n'
if s.count(cycle)!=1:
    raise SystemExit('cycle5 invocation mismatch')
s=s.replace(cycle,"  close_entry_gate 'FULL_CYCLE_REFRESH_IN_PROGRESS'\n"+cycle)
loop='  while true; do\n'
if s.count(loop)!=1:
    raise SystemExit('wait loop mismatch')
s=s.replace(loop,loop+'    enforce_entry_freshness\n')
sys.stdout.write(s)
PY_PATCH
  cat "$tmp" > "$LAUNCHER"
  rm -f "$tmp"
fi

if ! bash -n "$LAUNCHER"; then
  cat "$backup" > "$LAUNCHER"
  echo 'LAUNCHER_SYNTAX_FAIL_ROLLBACK'
  exit 4
fi
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=6' "$LAUNCHER"
grep -q "close_entry_gate 'FULL_CYCLE_REFRESH_IN_PROGRESS'" "$LAUNCHER"
grep -q 'enforce_entry_freshness' "$LAUNCHER"

echo 'ENTRY_FRESHNESS_MAX_AGE_SEC=6'
echo 'FULL_SCAN_ENTRY_GATE=CLOSED_DURING_REFRESH'
echo 'POSITION_EXIT_PATH_CHANGED=FALSE'
echo 'RISK_LIMITS_CHANGED=FALSE'
echo 'SECURITY_GATES_WEAKENED=FALSE'

if ! sudo -n /bin/systemctl restart "$SERVICE"; then
  cat "$backup" > "$LAUNCHER"
  echo 'RESTART_DENIED_ROLLBACK'
  exit 5
fi
sleep 3
if ! sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null; then
  cat "$backup" > "$LAUNCHER"
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo 'SERVICE_INACTIVE_ROLLBACK'
  exit 6
fi

echo '=== POST-RESTART GATE ==='
node - "$GATE" "$SIG" <<'NODE_STATUS' || true
const fs=require('fs');
try {
 const g=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),s=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
 const age=(Date.now()-Date.parse(s.timestamp||0))/1000;
 console.log(JSON.stringify({allowed:g.allowed,reasons:g.reasons,fastGuard:g.fastGuard||null,signalAgeSec:Number.isFinite(age)?Number(age.toFixed(2)):null},null,2));
} catch(e){console.log('POST_GATE_READ_FAIL')}
NODE_STATUS

echo 'V305_R2_LIVE_FRESHNESS_GUARD_ACTIVE_PASS'
