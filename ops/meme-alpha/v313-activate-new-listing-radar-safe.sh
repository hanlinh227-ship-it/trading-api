#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC="$APP/src"
SCANNER="$SRC/scanner.js"
RUN="$APP/run-paper.sh"
RADAR_SRC="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/v312-new-listing-radar.js"
RADAR="$SRC/new-listing-radar.js"
SERVICE=meme-alpha-paper.service
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BKP="$APP/runtime-status/v313-backup-$STAMP"
mkdir -p "$BKP"

fail(){ echo "V313_FAIL=$1"; exit 1; }
for p in "$RADAR_SRC" "$SCANNER" "$RUN"; do [ -r "$p" ] || fail "UNREADABLE_$p"; done
[ -w "$SRC" ] || fail SRC_DIR_NOT_WRITABLE
[ -w "$SCANNER" ] || fail SCANNER_NOT_WRITABLE
[ -w "$RUN" ] || fail RUN_PAPER_NOT_WRITABLE
cp -p "$SCANNER" "$BKP/scanner.js"
cp -p "$RUN" "$BKP/run-paper.sh"
[ -e "$RADAR" ] && cp -p "$RADAR" "$BKP/new-listing-radar.js" || true

echo "V313_BACKUP=$BKP"
rollback(){
  echo V313_ROLLBACK_START=TRUE
  local srt="$SRC/.scanner-v313-rollback.$$.js"
  local rrt="$APP/.run-paper-v313-rollback.$$.sh"
  cp "$BKP/scanner.js" "$srt" || true
  mv -f "$srt" "$SCANNER" || true
  cp "$BKP/run-paper.sh" "$rrt" || true
  chmod 775 "$rrt" || true
  mv -f "$rrt" "$RUN" || true
  if [ -f "$BKP/new-listing-radar.js" ]; then cp "$BKP/new-listing-radar.js" "$RADAR" || true; else rm -f "$RADAR" || true; fi
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo V313_ROLLBACK_DONE=TRUE
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi' EXIT

# 1) Install radar source.
rtmp="$SRC/.new-listing-radar-v313.$$.js"
cp "$RADAR_SRC" "$rtmp"
/usr/bin/node --check "$rtmp"
mv -f "$rtmp" "$RADAR"

# 2) Enrich scanner using radar ONLY for mints already discovered by Jupiter.
stmp="$SRC/.scanner-v313.$$.js"
python3 - "$SCANNER" > "$stmp" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if 'NEW_LISTING_RADAR_V312' not in s:
    a='const DISCOVERY_CACHE_MAX_AGE_MS = 5 * 60 * 1000;'
    if s.count(a)!=1: raise SystemExit('SCANNER_CONST_ANCHOR')
    s=s.replace(a,a+'''\n\n// NEW_LISTING_RADAR_V312: discovery-only cross-confirmation.\nconst NEW_LISTING_RADAR =\n  "/opt/meme-alpha/app/runtime-status/new-listing-radar.json";\n''')

    a='''  const liveRows =\n    [...map.values()];'''
    if s.count(a)!=1: raise SystemExit('SCANNER_LIVEROWS_ANCHOR')
    b='''  // NEW_LISTING_RADAR_V312_MERGE\n  // Safety invariant: radar-only mints are NOT inserted into the scanner map.\n  let radarHealthy = false;\n  let radarMatches = 0;\n  try {\n    const radar = JSON.parse(fs.readFileSync(NEW_LISTING_RADAR, "utf8"));\n    const radarAgeMs = Date.now() - Date.parse(radar.updatedAt || 0);\n    radarHealthy = radar.status === "HEALTHY" && Number.isFinite(radarAgeMs) && radarAgeMs >= 0 && radarAgeMs <= 20000;\n    if (radarHealthy) {\n      for (const r of (radar.candidates || [])) {\n        const existing = map.get(r.mint);\n        if (!existing) continue;\n        existing.sources = Array.isArray(existing.sources) ? existing.sources : [];\n        if (!existing.sources.includes("dex-new-listing-radar")) existing.sources.push("dex-new-listing-radar");\n        existing.newListingRadar = {\n          pairCreatedAt:r.pairCreatedAt||null,\n          pairAgeSec:Number.isFinite(Number(r.pairAgeSec))?Number(r.pairAgeSec):null,\n          preScore:n(r.preScore), liquidityUsd:n(r.liquidityUsd),\n          buys5m:n(r.buys5m), sells5m:n(r.sells5m),\n          sources:Array.isArray(r.sources)?r.sources:[]\n        };\n        if (!existing.firstPool && r.pairCreatedAt) existing.firstPool={id:r.pairAddress||null,createdAt:r.pairCreatedAt};\n        radarMatches++;\n      }\n    }\n  } catch {}\n  console.log(`NEW_LISTING_RADAR_MATCHES=${radarMatches} HEALTHY=${radarHealthy}`);\n\n  const liveRows =\n    [...map.values()];'''
    s=s.replace(a,b)

    a='  const priceChange = n(s.priceChange);'
    if s.count(a)!=1: raise SystemExit('SCANNER_PRICE_ANCHOR')
    s=s.replace(a,a+'''\n\n  // NEW_LISTING_RADAR_V312_AGE\n  const poolCreatedMs = Date.parse(token.firstPool?.createdAt || token.newListingRadar?.pairCreatedAt || "");\n  const pairAgeMin = Number.isFinite(poolCreatedMs) ? Math.max(0,(Date.now()-poolCreatedMs)/60000) : Infinity;\n  const radarPreScore = n(token.newListingRadar?.preScore);\n''')

    a='  // Discovery agreement: max 10'
    if s.count(a)!=1: raise SystemExit('SCANNER_SCORE_ANCHOR')
    b='''  // NEW_LISTING_RADAR_V312_RECENCY_BONUS\n  // Recency can rank a safe candidate earlier but cannot bypass any hard gate.\n  const newListingFlowOk = liquidity >= cfg.minLiquidityUsd && netBuyers > 0 && organicRatio >= 0.10;\n  if (newListingFlowOk && pairAgeMin <= 5) { score += 10; reasons.push("NEW_LISTING_EARLY_FLOW"); }\n  else if (newListingFlowOk && pairAgeMin <= 15) { score += 7; reasons.push("NEW_LISTING_FRESH_FLOW"); }\n  else if (newListingFlowOk && pairAgeMin <= 60) { score += 4; reasons.push("NEW_LISTING_RECENT_FLOW"); }\n  if (newListingFlowOk && radarPreScore >= 70) { score += 3; reasons.push("DEX_RADAR_CONFIRMATION"); }\n\n'''
    s=s.replace(a,b+a)

    a='    launchpad: token.launchpad || null,'
    if s.count(a)!=1: raise SystemExit('SCANNER_OUTPUT_ANCHOR')
    s=s.replace(a,a+'''\n    pairAgeMin: Number.isFinite(pairAgeMin) ? Number(pairAgeMin.toFixed(3)) : null,\n    radarPreScore,\n    newListingRadar: token.newListingRadar || null,''')
sys.stdout.write(s)
PY
/usr/bin/node --check "$stmp"
mv -f "$stmp" "$SCANNER"

# 3) Start independent radar every 5 seconds inside paper service cgroup.
runtmp="$APP/.run-paper-v313.$$.sh"
python3 - "$RUN" > "$runtmp" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
if 'NEW_LISTING_RADAR_LOOP_V312' not in s:
    a='FAILURE_BACKOFF_SEC=30'
    if s.count(a)!=1: raise SystemExit('RUN_PAPER_ANCHOR')
    b='''FAILURE_BACKOFF_SEC=30\n\n# NEW_LISTING_RADAR_LOOP_V312\nRADAR_PID=""\nstart_new_listing_radar() {\n  (\n    while true; do\n      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js || echo "NEW_LISTING_RADAR_CYCLE_FAILED"\n      sleep 5\n    done\n  ) &\n  RADAR_PID=$!\n  echo "NEW_LISTING_RADAR_PID=$RADAR_PID"\n}\ncleanup_new_listing_radar() {\n  [ -n "${RADAR_PID:-}" ] && kill "$RADAR_PID" 2>/dev/null || true\n}\ntrap cleanup_new_listing_radar EXIT TERM INT\nstart_new_listing_radar'''
    s=s.replace(a,b)
sys.stdout.write(s)
PY
/bin/bash -n "$runtmp"
chmod 775 "$runtmp"
mv -f "$runtmp" "$RUN"

# 4) Pre-restart invariants.
/usr/bin/node --check "$RADAR"
/usr/bin/node --check "$SCANNER"
/bin/bash -n "$RUN"
[ -x "$RUN" ] || fail RUN_PAPER_NOT_EXECUTABLE
grep -q 'DISCOVERY_ONLY_NEVER_GRANTS_ENTRY' "$RADAR"
grep -q 'radar-only mints are NOT inserted' "$SCANNER"
grep -q 'TOO_FEW_HOLDERS' "$SCANNER"
grep -q 'LOW_LIQUIDITY' "$SCANNER"
grep -q 'MINT_AUTHORITY_ACTIVE' "$SCANNER"
grep -q 'FREEZE_AUTHORITY_ACTIVE' "$SCANNER"
grep -q 'TOP_HOLDERS_TOO_CONCENTRATED' "$SCANNER"
grep -q 'const MAX_SELLABILITY_CHECKS_V216=3' "$SCANNER"
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=6' "$RUN"
echo V313_PRE_RESTART_INVARIANTS=PASS

sudo -n /bin/systemctl restart "$SERVICE" || fail PAPER_RESTART_FAILED
sleep 3
sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null || fail PAPER_NOT_ACTIVE

# 5) Radar health verification.
RSTATE="$APP/runtime-status/new-listing-radar.json"
radar_ok=0
for i in $(seq 1 20); do
  sleep 2
  row=$(/usr/bin/node - "$RSTATE" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const age=(Date.now()-Date.parse(x.updatedAt||0))/1000;console.log([x.status||'',x.healthySources||0,x.currentFeedMints||0,(x.candidates||[]).length,Number.isFinite(age)?age.toFixed(2):'999'].join('|'))}catch{}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r status hs mints count age <<< "$row"
  echo "RADAR_VERIFY status=$status healthySources=$hs feedMints=$mints candidates=$count ageSec=$age"
  if [ "$status" = HEALTHY ] && [ "${hs:-0}" -ge 2 ] && [ "${mints:-0}" -gt 0 ]; then radar_ok=1; break; fi
done
[ "$radar_ok" -eq 1 ] || fail RADAR_NOT_HEALTHY

# 6) Scanner/signal verification. Radar match may legitimately be zero at an instant.
SIG="$APP/runtime-status/signal-snapshot.json"
pre=$(/usr/bin/node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(x.timestamp||x.updatedAt||x.generatedAt||''))}catch{}
NODE
)
sig_ok=0
for i in $(seq 1 50); do
  sleep 2
  row=$(/usr/bin/node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const t=String(x.timestamp||x.updatedAt||x.generatedAt||'');const age=(Date.now()-Date.parse(t))/1000;const h=x.sourceHealth||{};console.log([t,Number.isFinite(age)?age.toFixed(2):'999',h.status||'',h.usingCache===true?'1':'0',(x.candidates||[]).filter(c=>c.newListingRadar).length].join('|'))}catch{}
NODE
)
  [ -n "$row" ] || continue
  IFS='|' read -r stamp age source cache matches <<< "$row"
  if [ -n "$stamp" ] && [ "$stamp" != "$pre" ]; then
    echo "SIGNAL_VERIFY stamp=$stamp ageSec=$age source=$source cache=$cache radarMatches=$matches"
    if [ "$source" = HEALTHY ] && [ "$cache" = 0 ]; then sig_ok=1; break; fi
  fi
done
[ "$sig_ok" -eq 1 ] || fail SIGNAL_NOT_HEALTHY

stat -c 'RUN_PAPER owner=%U group=%G mode=%a size=%s' "$RUN"
stat -c 'SCANNER owner=%U group=%G mode=%a size=%s' "$SCANNER"
echo V313_NEW_LISTING_RADAR_ACTIVE_PASS
trap - EXIT
