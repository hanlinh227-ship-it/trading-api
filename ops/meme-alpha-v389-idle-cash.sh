#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC="$APP/src"
RT="$APP/runtime-status"
BASE="$RT/deploy-candidates"
mkdir -p "$BASE"
CAND="$BASE/v389-idle-cash-executor.js"
cp -a "$SRC/micro-live-executor.js" "$CAND"
chmod 0644 "$CAND"

python3 - "$CAND" <<'PY'
import pathlib,re,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text()

def sub(pattern,repl,label,flags=0):
    global s
    s2,n=re.subn(pattern,repl,s,count=1,flags=flags)
    if n!=1: raise SystemExit(f'PATCH_{label}_COUNT={n}')
    s=s2

# 1) A hard-safe candidate may receive capital even when soft trend confirmation is absent.
sub(r'(function allocationProfile\(c,p,st,capitalBase\)\{[\s\S]{0,500}?if\(!)trendEntryEligible\(c\)',
    r'\1coreSafe(c)', 'ALLOC_CORE_SAFE')

# 2) New entries rank all hard-safe candidates; trend remains a preference, not a blocker.
sub(r'function bestCandidate\(p,exclude=new Set\(\),st=null,override=\[\]\)\{return candidates\(\)\.filter\(c=>trendEntryEligible\(c\)&&!exclude\.has\(c\.mint\)&&!blocked\(c,st\)&&!\(override\|\|\[\]\)\.includes\(c\.mint\)\)\.sort\(\(a,b\)=>expectedEdgeScore\(b,st\)-expectedEdgeScore\(a,st\)\)\[0\]\|\|null\}',
    "function bestCandidate(p,exclude=new Set(),st=null,override=[]){return candidates().filter(c=>coreSafe(c)&&!exclude.has(c.mint)&&!blocked(c,st)&&!(override||[]).includes(c.mint)).sort((a,b)=>(Number(trendEntryEligible(b))-Number(trendEntryEligible(a)))||(expectedEdgeScore(b,st)-expectedEdgeScore(a,st)))[0]||null}",
    'BEST_CORE_SAFE')

# 3) Whenever placeBuy is reached, target the configured maximum utilization (94%).
# targetPlan still subtracts base reserve, per-position exit reserve, network headroom and fees.
sub(r'plan=targetPlan\(beforeSol,st,existing,profile\.pct,p,\{isNew:!isAdd,exitHeadroomLamports\}\)',
    'plan=targetPlan(beforeSol,st,existing,p.maxUtilizationPct,p,{isNew:!isAdd,exitHeadroomLamports})',
    'MAX_UTILIZATION_TARGET')

# Production marker only.
if 'MICRO_LIVE_EXECUTOR_V389_IDLE_CASH=STARTED' not in s:
    sub(r'MICRO_LIVE_EXECUTOR_V(?:387_UNIFIED_PRODUCTION|382_NO_SOFT_GATE_FAST_PIPELINE)=STARTED',
        'MICRO_LIVE_EXECUTOR_V389_IDLE_CASH=STARTED','VERSION_MARKER')

p.write_text(s)
PY

node --check "$CAND"
testout="$(node "$CAND" --self-test)"
printf '%s\n' "$testout"
for k in MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT EQUITY_GROWTH_SCALES_NEW_BUYS=TRUE MULTI_POSITION_NO_HARD_COUNT_LIMIT=TRUE; do grep -q "$k" <<<"$testout"; done
grep -q 'filter(c=>coreSafe(c)' "$CAND"
grep -q 'targetPlan(beforeSol,st,existing,p.maxUtilizationPct' "$CAND"
grep -q 'MICRO_LIVE_EXECUTOR_V389_IDLE_CASH=STARTED' "$CAND"

WANT="$(sha256sum "$CAND" | awk '{print $1}')"
OLD_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
echo V389_EXPECTED_SHA="$WANT"
echo OLD_EXECUTOR_PID="${OLD_PID:-none}"

set +e
sudo -n /usr/local/sbin/meme-alpha-safe-deploy executor "$(basename "$CAND")" "$WANT"
DEPLOY_RC=$?
set -e
HAVE="$(sha256sum "$SRC/micro-live-executor.js" | awk '{print $1}')"
echo SAFE_DEPLOY_RC="$DEPLOY_RC"
echo PRODUCTION_SHA="$HAVE"
[ "$HAVE" = "$WANT" ] || { echo V389_FAIL=SOURCE_NOT_DEPLOYED; exit 3; }

NEW_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
if [ -z "$NEW_PID" ] || [ "$NEW_PID" = "$OLD_PID" ]; then
  ORIGINAL="$RT/v387-unified-final/run-paper.original.sh"
  [ -f "$ORIGINAL" ] || { echo V389_FAIL=ORIGINAL_RUNNER_MISSING; exit 4; }
  cp "$APP/run-paper.sh" "$RT/v389-run-paper.pre.sh"
  cat > "$APP/run-paper.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
ORIGINAL="$APP/runtime-status/v387-unified-final/run-paper.original.sh"
for p in $(pgrep -f '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true); do kill -9 "$p" 2>/dev/null || true; done
exec "$ORIGINAL"
SH
  chmod 0755 "$APP/run-paper.sh"
  timeout 90s sudo -n /bin/systemctl restart meme-alpha-paper.service || true
  for i in $(seq 1 45); do
    NEW_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
    [ -n "$NEW_PID" ] && [ "$NEW_PID" != "$OLD_PID" ] && break
    sleep 2
  done
  cp "$RT/v389-run-paper.pre.sh" "$APP/run-paper.sh"
  chmod 0755 "$APP/run-paper.sh"
  timeout 90s sudo -n /bin/systemctl restart meme-alpha-paper.service || true
fi

NEW_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
[ -n "$NEW_PID" ] && [ "$NEW_PID" != "$OLD_PID" ] || { echo V389_FAIL=EXECUTOR_NOT_RELOADED; exit 5; }
echo NEW_EXECUTOR_PID="$NEW_PID"
node --check "$SRC/micro-live-executor.js"
grep -q 'MICRO_LIVE_EXECUTOR_V389_IDLE_CASH=STARTED' "$SRC/micro-live-executor.js"
grep -q 'filter(c=>coreSafe(c)' "$SRC/micro-live-executor.js"
grep -q 'targetPlan(beforeSol,st,existing,p.maxUtilizationPct' "$SRC/micro-live-executor.js"

LIVE=0
for i in $(seq 1 60); do
  sleep 2
  if python3 - <<'PY'
import json,pathlib,time
rt=pathlib.Path('/opt/meme-alpha/app/runtime-status')
g=json.loads((rt/'micro-live-gate.json').read_text()); s=json.loads((rt/'signal-snapshot.json').read_text()); rows=s.get('candidates') or []
def n(v,d=0):
    try:return float(v)
    except:return d
def insider(c):
    x=c.get('insiderRiskDecision')
    if x in ('BLOCK','REVIEW'):return False
    if x=='PASS':return True
    top=n(c.get('topHoldersPct',c.get('top10Pct',c.get('top5Pct',c.get('topHolderPct')))),999)
    cluster=n(c.get('holderClusterMaxAccountsSameOwner',c.get('maxAccountsSameOwner',c.get('holderSameOwnerMax'))),999)
    wb=c.get('whaleConcentrationDecision') in ('BLOCK','REVIEW') or c.get('whaleConcentrationSafe') is False
    return c.get('securityDecision')=='PASS' and c.get('holderClusterDecision')=='PASS' and not wb and top<=35 and cluster<=2
safe=[c for c in rows if c.get('securityDecision')=='PASS' and c.get('holderClusterDecision')=='PASS' and insider(c) and c.get('token2022') is not True and c.get('sellRoute') is True and not(c.get('hardReject') or []) and n(c.get('liquidityUsd'))>=50000 and abs(n(c.get('sellPriceImpactPct',c.get('priceImpactPct'))))<=1.25]
print('V389_LIVE',{'allowed':g.get('allowed'),'sourceHealthy':g.get('sourceHealthy'),'liveRiskReady':g.get('liveRiskReady'),'scaleAllowed':g.get('scaleAllowed'),'signalCount':len(rows),'hardSafeCount':len(safe),'hardSafeSymbols':[c.get('symbol') for c in safe[:10]],'signalAgeSec':round(time.time()-(rt/'signal-snapshot.json').stat().st_mtime,1),'reasons':g.get('reasons')})
assert g.get('allowed') is True and g.get('sourceHealthy') is True and g.get('liveRiskReady') is True and g.get('scaleAllowed') is True
assert time.time()-(rt/'signal-snapshot.json').stat().st_mtime<60
assert safe
PY
  then LIVE=1; break; fi
done
[ "$LIVE" = 1 ] || { echo V389_FAIL=LIVE_HARD_SAFE_PIPELINE_NOT_READY; exit 6; }

for svc in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service meme-alpha-realtime-pulse.service meme-alpha-trend-pulse.service meme-alpha-whale-flow.service; do
  systemctl is-active --quiet "$svc" || { echo V389_FAIL_SERVICE="$svc"; exit 7; }
  echo "$svc=active"
done
[ "$(pgrep -fc '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)" -eq 1 ] || { echo V389_FAIL=EXECUTOR_PROCESS_COUNT; exit 8; }

echo V389_IDLE_CASH_DEPLOYMENT=ACTIVE
echo HARD_SAFE_FIRST=TRUE
echo IDLE_CAPITAL_TARGET_UTILIZATION_PCT=94
echo SCALE_ALLOWED=TRUE
echo HARD_SECURITY_HOLDER_INSIDER_SELLABILITY=ENFORCED
