#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
CFG="$APP/config/runtime.json"
SIG="$APP/runtime-status/signal-snapshot.json"
SERVICE=meme-alpha-paper.service
TARGET_MS=3000
MAX_ALLOWED_MS=5000
cd "$APP"

echo '=== V301 SCANNER FRESHNESS AUTOTUNE ==='
[ -r "$CFG" ] && [ -w "$CFG" ] || { echo 'CONFIG_NOT_WRITABLE'; exit 2; }

# Prove scannerIntervalMs is consumed outside the config before touching production.
echo '=== CONFIG CONSUMERS ==='
refs=$(grep -Rns --exclude='runtime.json' --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=code-backups 'scannerIntervalMs' run-paper.sh src 2>/dev/null || true)
printf '%s\n' "$refs"
[ -n "$refs" ] || { echo 'SCANNER_INTERVAL_CONSUMER_NOT_FOUND_ABORT'; exit 3; }

current=$(node -e "const x=require(process.argv[1]); const v=Number(x.scannerIntervalMs); if(!Number.isFinite(v)) process.exit(2); process.stdout.write(String(v))" "$CFG")
echo "SCANNER_INTERVAL_BEFORE_MS=$current"

# Safety envelope: only tune a known slow interval; never touch risk/security/execution fields.
if [ "$current" -le "$MAX_ALLOWED_MS" ]; then
  echo 'SCANNER_INTERVAL_ALREADY_FAST'
else
  backup="$APP/runtime-status/runtime-v301-$(date -u +%Y%m%dT%H%M%SZ).json.bak"
  cp -p "$CFG" "$backup"
  echo "BACKUP=$backup"
  tmp=$(mktemp)
  node - "$CFG" "$TARGET_MS" > "$tmp" <<'NODE'
const fs=require('fs');
const f=process.argv[2], target=Number(process.argv[3]);
const x=JSON.parse(fs.readFileSync(f,'utf8'));
if(!Number.isFinite(Number(x.scannerIntervalMs))) throw new Error('scannerIntervalMs missing');
const before=JSON.stringify(x);
x.scannerIntervalMs=target;
// Immutable keys are intentionally untouched; this assertion detects accidental mutation.
const riskKeys=['mode','maxPortfolioExposurePct','maxPriceImpactPct','paperStartingEquitySol'];
const y=JSON.parse(before);
for(const k of riskKeys) if(JSON.stringify(x[k])!==JSON.stringify(y[k])) throw new Error(`immutable key changed: ${k}`);
process.stdout.write(JSON.stringify(x,null,2)+'\n');
NODE
  cat "$tmp" > "$CFG"
  rm -f "$tmp"
  echo "SCANNER_INTERVAL_APPLIED_MS=$TARGET_MS"

  if ! sudo -n /bin/systemctl restart "$SERVICE"; then
    cat "$backup" > "$CFG"
    echo 'RESTART_DENIED_ROLLED_BACK'
    exit 4
  fi
fi

sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null || { echo 'PAPER_SERVICE_NOT_ACTIVE'; exit 5; }

echo '=== FRESHNESS HEALTH WINDOW ==='
start_ts=$(date +%s)
last_stamp=''
updates=0
min_age=999999
max_age=0
source_bad=0
for i in $(seq 1 15); do
  sleep 2
  [ -r "$SIG" ] || { echo "SAMPLE_$i SIGNAL_MISSING"; continue; }
  row=$(node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');
try {
 const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const stamp=x.timestamp||x.updatedAt||x.generatedAt||null;
 const ms=stamp?Date.parse(stamp):NaN;
 const age=Number.isFinite(ms)?Math.max(0,(Date.now()-ms)/1000):999999;
 const sh=x.sourceHealth||{};
 console.log([stamp||'',age.toFixed(2),String(sh.status||''),sh.usingCache===true?'1':'0',sh.allowNewEntries===true?'1':'0'].join('|'));
} catch(e) {}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r stamp age status using_cache allow_entries <<< "$row"
  echo "SAMPLE_$i stamp=$stamp ageSec=$age source=$status cache=$using_cache allowNewEntries=$allow_entries"
  if [ -n "$stamp" ] && [ "$stamp" != "$last_stamp" ]; then updates=$((updates+1)); last_stamp="$stamp"; fi
  age_i=${age%.*}; [ "$age_i" -lt "$min_age" ] && min_age=$age_i; [ "$age_i" -gt "$max_age" ] && max_age=$age_i
  if [ "$using_cache" = '1' ]; then source_bad=1; fi
done

echo "SIGNAL_UNIQUE_UPDATES=$updates"
echo "SIGNAL_MIN_AGE_SEC=$min_age"
echo "SIGNAL_MAX_AGE_SEC=$max_age"
final=$(node -e "const x=require(process.argv[1]); process.stdout.write(String(x.scannerIntervalMs))" "$CFG")
echo "SCANNER_INTERVAL_FINAL_MS=$final"

# Fail closed: no fresh updates, service/source unhealthy => restore prior config if a backup was made.
if [ "$updates" -lt 2 ] || [ "$min_age" -gt 8 ] || [ "$source_bad" -eq 1 ]; then
  if [ -n "${backup:-}" ] && [ -r "$backup" ]; then
    cat "$backup" > "$CFG"
    sudo -n /bin/systemctl restart "$SERVICE" || true
    echo 'V301_HEALTH_FAIL_ROLLBACK=TRUE'
  fi
  exit 6
fi

echo 'RISK_LIMITS_CHANGED=FALSE'
echo 'SECURITY_GATES_CHANGED=FALSE'
echo 'LIVE_MODE_CHANGED=FALSE'
echo 'V301_SCANNER_FRESHNESS_AUTOTUNE_PASS'
