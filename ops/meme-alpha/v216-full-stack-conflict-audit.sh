#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.16 FULL STACK CONFLICT AUDIT ==='
for u in meme-alpha-paper.service meme-alpha-trend-pulse.service meme-alpha-micro-live.service meme-alpha-signer.service; do
  printf 'UNIT=%s ACTIVE=%s PID=%s START=%s\n' "$u" "$(systemctl is-active "$u" 2>/dev/null || true)" "$(systemctl show "$u" -p MainPID --value 2>/dev/null || true)" "$(systemctl show "$u" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
done
python3 - <<'PY'
import os,time,json
files=[
'/opt/meme-alpha/app/runtime-status/signal-snapshot.json',
'/opt/meme-alpha/app/runtime-status/micro-live-gate.json',
'/opt/meme-alpha/app/runtime-status/trend-pulse.json',
'/var/lib/meme-alpha/data/paper/scanner-latest.json',
'/opt/meme-alpha/app/runtime-status/risk.json',
'/opt/meme-alpha/app/runtime-status/source-health.json',
'/opt/meme-alpha/app/runtime-status/validation.json',
]
print('--- FILE AGES ---')
for p in files:
 try: print(f'{p} age={time.time()-os.path.getmtime(p):.1f}s size={os.path.getsize(p)}')
 except Exception as e: print(f'{p} MISSING_OR_DENIED={type(e).__name__}')
for p,label in [('/opt/meme-alpha/app/runtime-status/micro-live-gate.json','GATE'),('/opt/meme-alpha/app/runtime-status/risk.json','RISK'),('/opt/meme-alpha/app/runtime-status/source-health.json','SOURCE')]:
 try:
  x=json.load(open(p));print(label+'='+json.dumps(x,separators=(',',':'))[:4000])
 except Exception as e: print(label+'_READ_FAIL='+type(e).__name__)
PY

echo '--- PAPER PIPELINE / PACKAGE ---'
cat package.json 2>/dev/null | sed -n '1,220p' || true
sed -n '1,240p' run-paper.sh 2>/dev/null || true

echo '--- EXECUTOR CRITICAL LOGIC ---'
for pat in 'st.position' 'positions' 'function entryPlan' 'function tier' 'maxUtilization' 'scaleIn' 'sellFraction' 'previewExitReturn' 'hardSafetyBroken' 'severeTrendBreak' 'softTrendWeak' 'gate.allowed' 'weakExitCount' 'maxSellPriceImpact' 'priceImpact'; do
 echo "### PATTERN=$pat";grep -n -F "$pat" src/micro-live-executor.js 2>/dev/null | head -80 || true
done

echo '--- EXECUTOR CONTEXT 1-420 ---'
sed -n '1,420p' src/micro-live-executor.js 2>/dev/null || true

echo '--- GATE CRITICAL LOGIC ---'
sed -n '1,320p' src/micro-live-gate.js 2>/dev/null || true

echo '--- RISK CRITICAL LOGIC ---'
sed -n '1,360p' src/risk.js 2>/dev/null || true

echo '--- HOLDER FASTFAIL RUNTIME MARKERS ---'
grep -n -E '2500|Promise.any|Promise.all|slice\(0,12\)|concurr|OPPORTUNITY_HOLDER' src/holder-cluster.js 2>/dev/null | head -120 || true

echo '--- SIGNER NONSECRET POLICY LOGIC ---'
# Only code/policy logic. Do not inspect key files or socket payloads.
grep -n -E 'def candidate_ok|file_fresh|trendPath|signalPath|maxBuyPriceImpactPct|maxSellPriceImpactPct|maxOrdersPerHour|arbitrary|buy_limit|dailyTurnover' /opt/meme-alpha-signer/ready_signer.py 2>/dev/null | head -180 || true

echo '--- PROCESS HOTSPOTS ---'
ps -eo pid,ppid,etimes,stat,%cpu,%mem,args | grep -E 'meme-alpha|holder-cluster|scanner.js|security.js|token2022|risk.js|micro-live' | grep -v grep | head -120 || true

echo V216_FULL_STACK_CONFLICT_AUDIT_PASS
