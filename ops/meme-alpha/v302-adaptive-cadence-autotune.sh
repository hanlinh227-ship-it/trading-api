#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
LAUNCHER="$APP/run-paper.sh"
SIG="$APP/runtime-status/signal-snapshot.json"
SERVICE=meme-alpha-paper.service
cd "$APP"

echo '=== V302 R2 ADAPTIVE CADENCE ACTIVATE + VERIFY ==='
[ -r "$LAUNCHER" ] && [ -w "$LAUNCHER" ] || { echo 'LAUNCHER_NOT_WRITABLE'; exit 2; }

# Hard safety constants must stay intact in both baseline and tuned states.
for expected in 'QUOTE_BACKOFF_FULL_GAP_SEC=30' 'DEGRADED_FULL_GAP_SEC=45' 'FAILURE_BACKOFF_SEC=30'; do
  grep -qx "$expected" "$LAUNCHER" || { echo "SAFETY_BASELINE_MISMATCH=$expected"; exit 3; }
done

baseline=0; tuned=0
if grep -qx 'TURBO_FULL_GAP_SEC=12' "$LAUNCHER" && grep -qx 'HEALTHY_FULL_GAP_SEC=15' "$LAUNCHER" && grep -qx 'ACTIVE_POSITION_TICK_SEC=5' "$LAUNCHER" && grep -qx 'IDLE_CHECK_SEC=5' "$LAUNCHER"; then baseline=1; fi
if grep -qx 'TURBO_FULL_GAP_SEC=3' "$LAUNCHER" && grep -qx 'HEALTHY_FULL_GAP_SEC=5' "$LAUNCHER" && grep -qx 'ACTIVE_POSITION_TICK_SEC=2' "$LAUNCHER" && grep -qx 'IDLE_CHECK_SEC=2' "$LAUNCHER"; then tuned=1; fi
[ "$baseline" -eq 1 ] || [ "$tuned" -eq 1 ] || { echo 'UNKNOWN_CADENCE_STATE_ABORT'; exit 4; }

if [ "$baseline" -eq 1 ]; then
  backup="$APP/runtime-status/run-paper-v302-$(date -u +%Y%m%dT%H%M%SZ).sh.bak"
  cp -p "$LAUNCHER" "$backup"
  tmp=$(mktemp)
  node - "$LAUNCHER" > "$tmp" <<'NODE'
const fs=require('fs'); const f=process.argv[2]; let s=fs.readFileSync(f,'utf8');
for(const [a,b] of [['TURBO_FULL_GAP_SEC=12','TURBO_FULL_GAP_SEC=3'],['HEALTHY_FULL_GAP_SEC=15','HEALTHY_FULL_GAP_SEC=5'],['ACTIVE_POSITION_TICK_SEC=5','ACTIVE_POSITION_TICK_SEC=2'],['IDLE_CHECK_SEC=5','IDLE_CHECK_SEC=2']]){const n=s.split(a).length-1;if(n!==1) throw new Error(`expected one ${a}, got ${n}`);s=s.replace(a,b)}
process.stdout.write(s);
NODE
  cat "$tmp" > "$LAUNCHER"; rm -f "$tmp"
  echo 'CADENCE_PATCHED_NOW=TRUE'
else
  backup=$(ls -1t "$APP"/runtime-status/run-paper-v302-*.sh.bak 2>/dev/null | head -1 || true)
  echo 'CADENCE_ALREADY_PATCHED_FROM_PRIOR_ATTEMPT=TRUE'
fi

# Verify exact tuned state and shell syntax. chmod is deliberately omitted: existing mode is already executable.
for expected in 'TURBO_FULL_GAP_SEC=3' 'HEALTHY_FULL_GAP_SEC=5' 'ACTIVE_POSITION_TICK_SEC=2' 'IDLE_CHECK_SEC=2' 'QUOTE_BACKOFF_FULL_GAP_SEC=30' 'DEGRADED_FULL_GAP_SEC=45' 'FAILURE_BACKOFF_SEC=30'; do grep -qx "$expected" "$LAUNCHER"; done
bash -n "$LAUNCHER"
stat -c 'LAUNCHER owner=%U group=%G mode=%a' "$LAUNCHER"

echo 'CADENCE_TARGET=TURBO_3S_HEALTHY_5S_ACTIVE_2S'
echo 'QUOTE_BACKOFF_PRESERVED=30S'
echo 'DEGRADED_BACKOFF_PRESERVED=45S'
echo 'RISK_LIMITS_CHANGED=FALSE'
echo 'SECURITY_GATES_CHANGED=FALSE'

pre_stamp=''
if [ -r "$SIG" ]; then pre_stamp=$(node -e "try{const x=require(process.argv[1]);process.stdout.write(String(x.timestamp||x.updatedAt||x.generatedAt||''))}catch{}" "$SIG"); fi
echo "PRE_SIGNAL_STAMP=$pre_stamp"

rollback(){
  if [ -n "${backup:-}" ] && [ -r "$backup" ] && grep -qx 'TURBO_FULL_GAP_SEC=12' "$backup"; then
    cat "$backup" > "$LAUNCHER"
    sudo -n /bin/systemctl restart "$SERVICE" || true
    echo "ROLLBACK_SOURCE=$backup"
  else
    echo 'ROLLBACK_SOURCE_UNAVAILABLE'
  fi
}

if ! sudo -n /bin/systemctl restart "$SERVICE"; then rollback; echo 'RESTART_DENIED'; exit 5; fi
sleep 2
if ! sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null; then rollback; echo 'SERVICE_INACTIVE'; exit 6; fi

echo 'PAPER_SERVICE_RESTARTED=TRUE'
echo '=== POST-TUNE SIGNAL WINDOW ==='
last="$pre_stamp"; new_updates=0; min_age=999999; max_age=0; cache_seen=0; healthy_seen=0
for i in $(seq 1 35); do
  sleep 2
  [ -r "$SIG" ] || { echo "SAMPLE_$i signal_missing"; continue; }
  row=$(node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs'); try {const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8')); const t=x.timestamp||x.updatedAt||x.generatedAt||''; const ms=Date.parse(t); const age=Number.isFinite(ms)?Math.max(0,(Date.now()-ms)/1000):999999; const h=x.sourceHealth||{}; console.log([t,age.toFixed(2),h.status||'',h.usingCache===true?'1':'0',h.allowNewEntries===true?'1':'0',Number(h.successfulSources||0),Number(h.failedSources||0)].join('|'));} catch(e){}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r stamp age status cache allow succ fail <<< "$row"
  echo "SAMPLE_$i ageSec=$age source=$status cache=$cache allow=$allow sources=$succ/$fail"
  if [ -n "$stamp" ] && [ "$stamp" != "$last" ]; then new_updates=$((new_updates+1)); last="$stamp"; fi
  ai=${age%.*}; [ "$ai" -lt "$min_age" ] && min_age=$ai; [ "$ai" -gt "$max_age" ] && max_age=$ai
  [ "$cache" = '1' ] && cache_seen=1
  [ "$status" = 'HEALTHY' ] && healthy_seen=1
  if [ "$new_updates" -ge 2 ] && [ "$min_age" -le 8 ]; then break; fi
done

echo "SIGNAL_NEW_UPDATES=$new_updates"
echo "SIGNAL_MIN_AGE_SEC=$min_age"
echo "SIGNAL_MAX_AGE_SEC=$max_age"
echo "SOURCE_HEALTHY_SEEN=$healthy_seen"
echo "CACHE_SEEN=$cache_seen"

if [ "$new_updates" -lt 1 ] || [ "$min_age" -gt 12 ]; then rollback; echo 'V302_FRESHNESS_VERIFY_FAIL_ROLLBACK=TRUE'; exit 7; fi

echo 'LIVE_MODE_CHANGED=FALSE'
echo 'V302_R2_ADAPTIVE_CADENCE_ACTIVE_PASS'
