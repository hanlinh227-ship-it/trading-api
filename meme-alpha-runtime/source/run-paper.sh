#!/bin/bash
set -u
cd /opt/meme-alpha/app || exit 1


# V328_LIVE_SCAN_ONLY
# The legacy systemd unit is still named meme-alpha-paper.service for compatibility,
# but it now performs discovery/risk/signal generation only. PAPER BUY/SELL execution
# is disabled and the old demo ledger is archived once by the service user.
LIVE_SCAN_ONLY=1
init_live_scan_only() {
  /usr/bin/node - <<'NODE_V328_INIT' 2>/dev/null || true
const fs=require('fs'),path=require('path');
const data='/var/lib/meme-alpha/data/paper';
const marker=path.join(data,'.v328-live-scan-only');
const runtime='/opt/meme-alpha/app/runtime-status';
try{
  fs.mkdirSync(data,{recursive:true});
  if(!fs.existsSync(marker)){
    const stamp=new Date().toISOString().replace(/[:.]/g,'-');
    const arc=path.join(data,'demo-archive-'+stamp);
    fs.mkdirSync(arc,{recursive:true});
    for(const n of ['state.json','validation.json','stress-test.json','risk-state.json','reaction-telemetry.json']){
      const p=path.join(data,n); if(fs.existsSync(p)) try{fs.copyFileSync(p,path.join(arc,n))}catch{}
    }
    const neutral={version:'LIVE_SCAN_ONLY_V328',mode:'LIVE_SCAN_ONLY',startingEquitySol:1,equitySol:1,highWaterEquitySol:1,realizedPnlSol:0,unrealizedPnlSol:0,openPositions:[],trades:[],paperExecutionEnabled:false,resetAt:new Date().toISOString()};
    const sp=path.join(data,'state.json'),tmp=sp+'.v328.tmp';fs.writeFileSync(tmp,JSON.stringify(neutral,null,2));fs.renameSync(tmp,sp);
    fs.writeFileSync(marker,JSON.stringify({mode:'LIVE_SCAN_ONLY',paperExecutionEnabled:false,archivedTo:arc,createdAt:new Date().toISOString()},null,2));
  }
  const out={version:'3.28.0',timestamp:new Date().toISOString(),mode:'LIVE_SCAN_ONLY',paperExecutionEnabled:false,liveExecutionOwnedBy:'meme-alpha-micro-live.service',scannerEnabled:true,radarEnabled:true,legacyUnitName:'meme-alpha-paper.service'};
  const op=path.join(runtime,'execution-separation.json'),ot=op+'.tmp';fs.writeFileSync(ot,JSON.stringify(out,null,2));fs.renameSync(ot,op);try{fs.chmodSync(op,0o664)}catch{}
  for(const [name,obj] of [['validation.json',{version:'DISABLED_V328',timestamp:new Date().toISOString(),readinessStatus:'DISABLED_LIVE_ONLY',completedLifecycleTrades:0}],['stress-test.json',{version:'DISABLED_V328',timestamp:new Date().toISOString(),status:'DISABLED_LIVE_ONLY'}]]){
    const p=path.join(runtime,name),t=p+'.v328.tmp';fs.writeFileSync(t,JSON.stringify(obj,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}
  }
}catch(e){}
NODE_V328_INIT
}
init_live_scan_only

# v1.1.2 adaptive cadence:
# - full discovery remains rate-limit aware; never tighter than 20s between full cycles
# - active positions receive ~5s mark/exit checks
# - no-position periods avoid pointless Dex calls
# - degraded source health automatically backs off
QUOTE_BACKOFF_FULL_GAP_SEC=30
TURBO_FULL_GAP_SEC=3
HEALTHY_FULL_GAP_SEC=5
DEGRADED_FULL_GAP_SEC=45
ACTIVE_POSITION_TICK_SEC=2
IDLE_CHECK_SEC=2
FAILURE_BACKOFF_SEC=30

# NEW_LISTING_RADAR_LOOP_V312
RADAR_PID=""
start_new_listing_radar() {
  (
    while true; do
      echo "RADAR_HEARTBEAT_START $(date -u +%Y-%m-%dT%H:%M:%SZ) user=$(id -un)" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || true
      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1
      sleep 6
    done
  ) &
  RADAR_PID=$!
  echo "NEW_LISTING_RADAR_PID=$RADAR_PID"
}
cleanup_new_listing_radar() {
  [ -n "${RADAR_PID:-}" ] && kill "$RADAR_PID" 2>/dev/null || true
}
trap cleanup_new_listing_radar EXIT TERM INT
start_new_listing_radar

# V305_LIVE_FRESHNESS_GUARD
LIVE_SIGNAL_MAX_AGE_SEC=60
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


open_positions_count() {
  /usr/bin/node - <<'NODE' 2>/dev/null
const fs=require('fs');
try {
  const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
  console.log(Array.isArray(s.openPositions)?s.openPositions.length:0);
} catch { console.log(0); }
NODE
}

source_profile() {
  /usr/bin/node - <<'NODE' 2>/dev/null
const fs=require('fs');
try {
  const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
  const age=h.checkedAt ? (Date.now()-new Date(h.checkedAt).getTime())/1000 : Infinity;
  const base=h.status==='HEALTHY' && h.allowNewEntries===true && h.usingCache!==true && Number(h.successfulSources)>=2 && age>=0 && age<180;
  let quotePressure=0;
  try {
    const q=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-latest.json','utf8'));
    quotePressure=(q.candidates||[]).filter(c=>String(c.sellQuoteError||'').includes('429')||String(c.sellQuoteError||'').includes('TRANSIENT_HTTP_429')).length;
  } catch {}
  const turbo=base && Number(h.successfulSources)>=4 && Number(h.failedSources||0)===0 && quotePressure===0;
  console.log(quotePressure>0?'QUOTE_BACKOFF':(turbo?'TURBO':(base?'HEALTHY':'DEGRADED')));
} catch { console.log('DEGRADED'); }
NODE
}

while true; do
  echo
  echo "=========================================="
  echo "MEME ALPHA FULL CYCLE $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "=========================================="

  FULL_START=$(date +%s)
  echo 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH'
  # V328: live scanner pipeline only; intentionally excludes position.js, validation.js and stress-test.js.
  /usr/bin/node src/scanner.js && \
  /usr/bin/node src/universe.js && \
  /usr/bin/node src/security.js && \
  /usr/bin/node src/token2022-audit.js && \
  /usr/bin/node src/holder-cluster.js && \
  /usr/bin/node src/persistence.js && \
  /usr/bin/node src/risk.js && \
  /usr/bin/node src/safe-signal-export.js && \
  /usr/bin/node src/micro-live-gate.js
  rc=$?

  if [ "$rc" -ne 0 ]; then
    echo "FULL_CYCLE_FAILED rc=$rc"
    close_entry_gate 'FULL_CYCLE_FAILED'
    echo "ADAPTIVE_BACKOFF=${FAILURE_BACKOFF_SEC}s"
    sleep "$FAILURE_BACKOFF_SEC"
    continue
  fi

  echo "FULL_CYCLE_COMPLETE"

  PROFILE=$(source_profile)
  if [ "$PROFILE" = "QUOTE_BACKOFF" ]; then
    GAP="$QUOTE_BACKOFF_FULL_GAP_SEC"
  elif [ "$PROFILE" = "TURBO" ]; then
    GAP="$TURBO_FULL_GAP_SEC"
  elif [ "$PROFILE" = "HEALTHY" ]; then
    GAP="$HEALTHY_FULL_GAP_SEC"
  else
    GAP="$DEGRADED_FULL_GAP_SEC"
  fi
  echo "ADAPTIVE_SOURCE_PROFILE=$PROFILE FULL_GAP=${GAP}s"

  WAIT_START=$(date +%s)
  while true; do
    enforce_entry_freshness
    NOW=$(date +%s)
    ELAPSED=$((NOW-WAIT_START))
    if [ "$ELAPSED" -ge "$GAP" ]; then
      break
    fi

    REM=$((GAP-ELAPSED))
    SLEEP_SEC="$IDLE_CHECK_SEC"
    if [ "$REM" -lt "$SLEEP_SEC" ]; then SLEEP_SEC="$REM"; fi
    [ "$SLEEP_SEC" -gt 0 ] && sleep "$SLEEP_SEC"
    echo "LIVE_SCAN_ONLY_WAIT $(date -u +"%Y-%m-%dT%H:%M:%SZ") paper_execution=disabled"
  done

done
