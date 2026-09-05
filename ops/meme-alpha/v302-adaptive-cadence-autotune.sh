#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LAUNCHER="$APP/run-paper.sh"
SIG="$APP/runtime-status/signal-snapshot.json"
SERVICE=meme-alpha-paper.service
cd "$APP"

echo '=== V302 ADAPTIVE CADENCE AUTOTUNE ==='
[ -r "$LAUNCHER" ] && [ -w "$LAUNCHER" ] || { echo 'LAUNCHER_NOT_WRITABLE'; exit 2; }

# Exact known baseline only. We intentionally preserve quote/degraded backoff.
for expected in \
 'QUOTE_BACKOFF_FULL_GAP_SEC=30' \
 'TURBO_FULL_GAP_SEC=12' \
 'HEALTHY_FULL_GAP_SEC=15' \
 'DEGRADED_FULL_GAP_SEC=45' \
 'ACTIVE_POSITION_TICK_SEC=5' \
 'IDLE_CHECK_SEC=5' \
 'FAILURE_BACKOFF_SEC=30'; do
  grep -qx "$expected" "$LAUNCHER" || { echo "BASELINE_MISMATCH=$expected"; exit 3; }
done

backup="$APP/runtime-status/run-paper-v302-$(date -u +%Y%m%dT%H%M%SZ).sh.bak"
cp -p "$LAUNCHER" "$backup"
echo "BACKUP=$backup"

tmp=$(mktemp)
node - "$LAUNCHER" > "$tmp" <<'NODE'
const fs=require('fs'); const f=process.argv[2]; let s=fs.readFileSync(f,'utf8');
const edits=new Map([
 ['TURBO_FULL_GAP_SEC=12','TURBO_FULL_GAP_SEC=3'],
 ['HEALTHY_FULL_GAP_SEC=15','HEALTHY_FULL_GAP_SEC=5'],
 ['ACTIVE_POSITION_TICK_SEC=5','ACTIVE_POSITION_TICK_SEC=2'],
 ['IDLE_CHECK_SEC=5','IDLE_CHECK_SEC=2']
]);
for(const [a,b] of edits){const n=s.split(a).length-1;if(n!==1) throw new Error(`expected exactly one ${a}, got ${n}`);s=s.replace(a,b)}
process.stdout.write(s);
NODE
cat "$tmp" > "$LAUNCHER"
rm -f "$tmp"
chmod 775 "$LAUNCHER"

# Guardrails that must remain unchanged.
grep -qx 'QUOTE_BACKOFF_FULL_GAP_SEC=30' "$LAUNCHER"
grep -qx 'DEGRADED_FULL_GAP_SEC=45' "$LAUNCHER"
grep -qx 'FAILURE_BACKOFF_SEC=30' "$LAUNCHER"
grep -qx 'TURBO_FULL_GAP_SEC=3' "$LAUNCHER"
grep -qx 'HEALTHY_FULL_GAP_SEC=5' "$LAUNCHER"
grep -qx 'ACTIVE_POSITION_TICK_SEC=2' "$LAUNCHER"
bash -n "$LAUNCHER" || { cat "$backup" > "$LAUNCHER"; echo 'SYNTAX_FAIL_ROLLBACK'; exit 4; }

echo 'CADENCE_APPLIED=TURBO_3S_HEALTHY_5S_ACTIVE_2S'
echo 'QUOTE_BACKOFF_PRESERVED=30S'
echo 'DEGRADED_BACKOFF_PRESERVED=45S'
echo 'RISK_LIMITS_CHANGED=FALSE'
echo 'SECURITY_GATES_CHANGED=FALSE'

if ! sudo -n /bin/systemctl restart "$SERVICE"; then
  cat "$backup" > "$LAUNCHER"
  echo 'RESTART_DENIED_ROLLBACK'
  exit 5
fi
sleep 2
if ! sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null; then
  cat "$backup" > "$LAUNCHER"
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo 'SERVICE_INACTIVE_ROLLBACK'
  exit 6
fi

echo '=== POST-TUNE SIGNAL WINDOW ==='
last=''; updates=0; min_age=999999; max_age=0; cache_seen=0; healthy_seen=0
for i in $(seq 1 25); do
  sleep 2
  [ -r "$SIG" ] || continue
  row=$(node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs'); try {const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8')); const t=x.timestamp||x.updatedAt||x.generatedAt||''; const ms=Date.parse(t); const age=Number.isFinite(ms)?Math.max(0,(Date.now()-ms)/1000):999999; const h=x.sourceHealth||{}; console.log([t,age.toFixed(2),h.status||'',h.usingCache===true?'1':'0',h.allowNewEntries===true?'1':'0',Number(h.successfulSources||0),Number(h.failedSources||0)].join('|'));} catch(e){}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r stamp age status cache allow succ fail <<< "$row"
  echo "SAMPLE_$i ageSec=$age source=$status cache=$cache allow=$allow sources=$succ/$fail"
  if [ -n "$stamp" ] && [ "$stamp" != "$last" ]; then updates=$((updates+1)); last="$stamp"; fi
  ai=${age%.*}; [ "$ai" -lt "$min_age" ] && min_age=$ai; [ "$ai" -gt "$max_age" ] && max_age=$ai
  [ "$cache" = '1' ] && cache_seen=1
  [ "$status" = 'HEALTHY' ] && healthy_seen=1
done

echo "SIGNAL_UNIQUE_UPDATES=$updates"
echo "SIGNAL_MIN_AGE_SEC=$min_age"
echo "SIGNAL_MAX_AGE_SEC=$max_age"
echo "SOURCE_HEALTHY_SEEN=$healthy_seen"
echo "CACHE_SEEN=$cache_seen"

# Fail closed only on a genuinely dead feed/service. Source backoff itself handles transient degradation/429.
if [ "$updates" -lt 1 ] || [ "$min_age" -gt 12 ]; then
  cat "$backup" > "$LAUNCHER"
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo 'V302_FRESHNESS_NO_IMPROVEMENT_ROLLBACK=TRUE'
  exit 7
fi

echo 'LIVE_MODE_CHANGED=FALSE'
echo 'V302_ADAPTIVE_CADENCE_AUTOTUNE_PASS'
