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
BKP="$APP/runtime-status/v312-backup-$STAMP"
mkdir -p "$BKP"

fail(){ echo "V312_FAIL=$1"; exit 1; }
[ -r "$RADAR_SRC" ] || fail RADAR_SOURCE_MISSING
[ -r "$SCANNER" ] || fail SCANNER_MISSING
[ -r "$RUN" ] || fail RUN_PAPER_MISSING
[ -w "$SRC" ] || fail SRC_DIR_NOT_WRITABLE
[ -w "$SCANNER" ] || fail SCANNER_NOT_WRITABLE
[ -w "$RUN" ] || fail RUN_PAPER_NOT_WRITABLE
cp -p "$SCANNER" "$BKP/scanner.js"
cp -p "$RUN" "$BKP/run-paper.sh"
[ -e "$RADAR" ] && cp -p "$RADAR" "$BKP/new-listing-radar.js" || true

echo "V312_BACKUP=$BKP"

rollback(){
  echo 'V312_ROLLBACK_START=TRUE'
  cp "$BKP/scanner.js" "$SCANNER" || true
  cp "$BKP/run-paper.sh" "$RUN" || true
  if [ -f "$BKP/new-listing-radar.js" ]; then cp "$BKP/new-listing-radar.js" "$RADAR" || true; else rm -f "$RADAR" || true; fi
  sudo -n /bin/systemctl restart "$SERVICE" || true
  echo 'V312_ROLLBACK_DONE=TRUE'
}
trap 'rc=$?; if [ $rc -ne 0 ]; then rollback; fi' EXIT

# Install radar atomically.
rtmp="$SRC/.new-listing-radar-v312.$$.js"
cp "$RADAR_SRC" "$rtmp"
/usr/bin/node --check "$rtmp"
mv -f "$rtmp" "$RADAR"

# Patch scanner: radar may ONLY enrich mints already seen by Jupiter. It never creates an entry candidate by itself.
stmp="$SRC/.scanner-v312.$$.js"
python3 - "$SCANNER" > "$stmp" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
if 'NEW_LISTING_RADAR_V312' not in s:
    anchor='const DISCOVERY_CACHE_MAX_AGE_MS = 5 * 60 * 1000;'
    if s.count(anchor)!=1: raise SystemExit('scanner radar const anchor mismatch')
    s=s.replace(anchor, anchor+'''\n\n// NEW_LISTING_RADAR_V312: discovery-only cross-confirmation.\nconst NEW_LISTING_RADAR =\n  "/opt/meme-alpha/app/runtime-status/new-listing-radar.json";\n''')

    anchor2='''  const liveRows =\n    [...map.values()];'''
    if s.count(anchor2)!=1: raise SystemExit('scanner liveRows anchor mismatch')
    merge='''  // NEW_LISTING_RADAR_V312_MERGE\n  // Safety invariant: radar-only mints are NOT inserted into the scanner map.\n  // A mint must already be present in Jupiter discovery so holder/audit/stats fields exist.\n  let radarHealthy = false;\n  let radarMatches = 0;\n  try {\n    const radar = JSON.parse(fs.readFileSync(NEW_LISTING_RADAR, "utf8"));\n    const radarAgeMs = Date.now() - Date.parse(radar.updatedAt || 0);\n    radarHealthy =\n      radar.status === "HEALTHY" &&\n      Number.isFinite(radarAgeMs) &&\n      radarAgeMs >= 0 &&\n      radarAgeMs <= 20000;\n\n    if (radarHealthy) {\n      for (const r of (radar.candidates || [])) {\n        const existing = map.get(r.mint);\n        if (!existing) continue;\n        existing.sources = Array.isArray(existing.sources) ? existing.sources : [];\n        if (!existing.sources.includes("dex-new-listing-radar"))\n          existing.sources.push("dex-new-listing-radar");\n        existing.newListingRadar = {\n          pairCreatedAt: r.pairCreatedAt || null,\n          pairAgeSec: Number.isFinite(Number(r.pairAgeSec)) ? Number(r.pairAgeSec) : null,\n          preScore: n(r.preScore),\n          liquidityUsd: n(r.liquidityUsd),\n          buys5m: n(r.buys5m),\n          sells5m: n(r.sells5m),\n          sources: Array.isArray(r.sources) ? r.sources : []\n        };\n        if (!existing.firstPool && r.pairCreatedAt) {\n          existing.firstPool = { id: r.pairAddress || null, createdAt: r.pairCreatedAt };\n        }\n        radarMatches++;\n      }\n    }\n  } catch {}\n\n  console.log(`NEW_LISTING_RADAR_MATCHES=${radarMatches} HEALTHY=${radarHealthy}`);\n\n  const liveRows =\n    [...map.values()];'''
    s=s.replace(anchor2,merge)

    anchor3='''  const priceChange = n(s.priceChange);'''
    if s.count(anchor3)!=1: raise SystemExit('scanner analyze price anchor mismatch')
    s=s.replace(anchor3,anchor3+'''\n\n  // NEW_LISTING_RADAR_V312_AGE\n  const poolCreatedMs = Date.parse(\n    token.firstPool?.createdAt ||\n    token.newListingRadar?.pairCreatedAt ||\n    ""\n  );\n  const pairAgeMin = Number.isFinite(poolCreatedMs)\n    ? Math.max(0, (Date.now() - poolCreatedMs) / 60000)\n    : Infinity;\n  const radarPreScore = n(token.newListingRadar?.preScore);\n''')

    anchor4='''  // Discovery agreement: max 10'''
    if s.count(anchor4)!=1: raise SystemExit('scanner scoring anchor mismatch')
    bonus='''  // NEW_LISTING_RADAR_V312_RECENCY_BONUS\n  // Recency never bypasses hard gates. It only helps a liquid, organic, net-buyer-positive\n  // token already discovered by Jupiter rise in the ranking before the opportunity cools.\n  const newListingFlowOk =\n    liquidity >= cfg.minLiquidityUsd &&\n    netBuyers > 0 &&\n    organicRatio >= 0.10;\n\n  if (newListingFlowOk && pairAgeMin <= 5) {\n    score += 10;\n    reasons.push("NEW_LISTING_EARLY_FLOW");\n  } else if (newListingFlowOk && pairAgeMin <= 15) {\n    score += 7;\n    reasons.push("NEW_LISTING_FRESH_FLOW");\n  } else if (newListingFlowOk && pairAgeMin <= 60) {\n    score += 4;\n    reasons.push("NEW_LISTING_RECENT_FLOW");\n  }\n  if (newListingFlowOk && radarPreScore >= 70) {\n    score += 3;\n    reasons.push("DEX_RADAR_CONFIRMATION");\n  }\n\n'''
    s=s.replace(anchor4,bonus+anchor4)

    anchor5='''    launchpad: token.launchpad || null,'''
    if s.count(anchor5)!=1: raise SystemExit('scanner output anchor mismatch')
    s=s.replace(anchor5,anchor5+'''\n    pairAgeMin: Number.isFinite(pairAgeMin) ? Number(pairAgeMin.toFixed(3)) : null,\n    radarPreScore,\n    newListingRadar: token.newListingRadar || null,''')
sys.stdout.write(s)
PY
/usr/bin/node --check "$stmp"
mv -f "$stmp" "$SCANNER"

# Patch paper launcher with a low-cost independent radar loop. Radar never touches entry gate.
runtmp="$APP/.run-paper-v312.$$.sh"
python3 - "$RUN" > "$runtmp" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
if 'NEW_LISTING_RADAR_LOOP_V312' not in s:
    anchor='FAILURE_BACKOFF_SEC=30'
    if s.count(anchor)!=1: raise SystemExit('run-paper anchor mismatch')
    block='''FAILURE_BACKOFF_SEC=30\n\n# NEW_LISTING_RADAR_LOOP_V312\nRADAR_PID=""\nstart_new_listing_radar() {\n  (\n    while true; do\n      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js || echo "NEW_LISTING_RADAR_CYCLE_FAILED"\n      sleep 5\n    done\n  ) &\n  RADAR_PID=$!\n  echo "NEW_LISTING_RADAR_PID=$RADAR_PID"\n}\ncleanup_new_listing_radar() {\n  [ -n "${RADAR_PID:-}" ] && kill "$RADAR_PID" 2>/dev/null || true\n}\ntrap cleanup_new_listing_radar EXIT TERM INT\nstart_new_listing_radar'''
    s=s.replace(anchor,block)
sys.stdout.write(s)
PY
/bin/bash -n "$runtmp"
mv -f "$runtmp" "$RUN"

# Exact invariants: keep all existing safety layers and v307 latency budget.
/usr/bin/node --check "$RADAR"
/usr/bin/node --check "$SCANNER"
/bin/bash -n "$RUN"
grep -q 'DISCOVERY_ONLY_NEVER_GRANTS_ENTRY' "$RADAR"
grep -q 'radar-only mints are NOT inserted' "$SCANNER"
grep -q 'TOO_FEW_HOLDERS' "$SCANNER"
grep -q 'LOW_LIQUIDITY' "$SCANNER"
grep -q 'MINT_AUTHORITY_ACTIVE' "$SCANNER"
grep -q 'FREEZE_AUTHORITY_ACTIVE' "$SCANNER"
grep -q 'TOP_HOLDERS_TOO_CONCENTRATED' "$SCANNER"
grep -q 'const MAX_SELLABILITY_CHECKS_V216=3' "$SCANNER"
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=6' "$RUN"

echo 'V312_SAFETY_INVARIANTS=PASS'

if ! sudo -n /bin/systemctl restart "$SERVICE"; then fail PAPER_RESTART_FAILED; fi
sleep 3
sudo -n /bin/systemctl is-active "$SERVICE" >/dev/null || fail PAPER_NOT_ACTIVE

# Verify radar becomes healthy and produces a feed.
RADAR_STATE="$APP/runtime-status/new-listing-radar.json"
radar_ok=0
for i in $(seq 1 20); do
  sleep 2
  if [ -r "$RADAR_STATE" ]; then
    row=$(/usr/bin/node - "$RADAR_STATE" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const age=(Date.now()-Date.parse(x.updatedAt||0))/1000;console.log([x.status||'',x.healthySources||0,x.currentFeedMints||0,(x.candidates||[]).length,Number.isFinite(age)?age.toFixed(2):'999'].join('|'))}catch{}
NODE
)
    IFS='|' read -r status hs mints count age <<< "$row"
    echo "RADAR_VERIFY status=$status healthySources=$hs feedMints=$mints candidates=$count ageSec=$age"
    if [ "$status" = HEALTHY ] && [ "${hs:-0}" -ge 2 ] && [ "${mints:-0}" -gt 0 ]; then radar_ok=1; break; fi
  fi
done
[ "$radar_ok" -eq 1 ] || fail RADAR_NOT_HEALTHY

# Verify at least one new signal arrives post restart, source not cache.
SIG="$APP/runtime-status/signal-snapshot.json"
pre=$(/usr/bin/node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(String(x.timestamp||x.updatedAt||x.generatedAt||''))}catch{}
NODE
)
sig_ok=0
for i in $(seq 1 45); do
  sleep 2
  row=$(/usr/bin/node - "$SIG" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const t=String(x.timestamp||x.updatedAt||x.generatedAt||'');const age=(Date.now()-Date.parse(t))/1000;const h=x.sourceHealth||{};console.log([t,Number.isFinite(age)?age.toFixed(2):'999',h.status||'',h.usingCache===true?'1':'0',(x.candidates||[]).filter(c=>c.newListingRadar).length].join('|'))}catch{}
NODE
)
  IFS='|' read -r stamp age sh cache matches <<< "$row"
  if [ -n "$stamp" ] && [ "$stamp" != "$pre" ]; then
    echo "SIGNAL_VERIFY stamp=$stamp ageSec=$age source=$sh cache=$cache radarMatches=$matches"
    if [ "$cache" = 0 ] && [ "$sh" = HEALTHY ]; then sig_ok=1; break; fi
  fi
done
[ "$sig_ok" -eq 1 ] || fail SIGNAL_VERIFY_FAILED

echo 'V312_NEW_LISTING_RADAR_ACTIVE_PASS'
trap - EXIT
