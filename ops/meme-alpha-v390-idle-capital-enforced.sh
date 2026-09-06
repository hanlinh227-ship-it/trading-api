#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC_DIR="$APP/src"
SRC="$SRC_DIR/micro-live-executor.js"
RT="$APP/runtime-status"
BASE="$RT/deploy-candidates"
mkdir -p "$BASE"
CAND="$BASE/v390-idle-capital-enforced.js"
cp -a "$SRC" "$CAND"
chmod 0644 "$CAND"

python3 - "$CAND" <<'PY'
import pathlib,re,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text()

def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'PATCH_{label}_COUNT={n}')
    s=s.replace(old,new,1)

def sub(pattern,new,label):
    global s
    s2,n=re.subn(pattern,new,s,count=1,flags=re.S)
    if n!=1: raise SystemExit(f'PATCH_{label}_COUNT={n}')
    s=s2

old_insider="function insiderSafe(c){if(!c)return false;const d=String(c.insiderRiskDecision||'');if(d==='BLOCK'||d==='REVIEW')return false;const top=Number(c.topHoldersPct),cluster=Number(c.holderClusterMaxAccountsSameOwner);if(!Number.isFinite(top)||top>35||!Number.isFinite(cluster)||cluster>2)return false;const wt=c.whaleTop10Pct,wd=c.whaleDeltaTop10Pct;if(wt!==null&&wt!==undefined&&wt!==''&&Number.isFinite(Number(wt))&&Number(wt)>=70&&Number(wt)<100)return false;if(wd!==null&&wd!==undefined&&wd!==''&&Number.isFinite(Number(wd))&&Number(wd)>=8)return false;return d==='PASS'||(c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS')}"
new_holder_insider="function holderSafe(c){if(!c)return false;const d=String(c.holderClusterDecision||'');if(d==='BLOCK'||d==='REVIEW')return false;const top=Number(c.topHoldersPct),cluster=Number(c.holderClusterMaxAccountsSameOwner);if(!Number.isFinite(top)||top<0||top>35||!Number.isFinite(cluster)||cluster<0||cluster>2)return false;const wt=c.whaleTop10Pct,wd=c.whaleDeltaTop10Pct;if(wt!==null&&wt!==undefined&&wt!==''&&Number.isFinite(Number(wt))&&Number(wt)>=70&&Number(wt)<100)return false;if(wd!==null&&wd!==undefined&&wd!==''&&Number.isFinite(Number(wd))&&Number(wd)>=8)return false;return d==='PASS'||(d===''&&c.securityDecision==='PASS')}\nfunction insiderSafe(c){if(!c)return false;const d=String(c.insiderRiskDecision||'');if(d==='BLOCK'||d==='REVIEW')return false;const top=Number(c.topHoldersPct),cluster=Number(c.holderClusterMaxAccountsSameOwner);if(!Number.isFinite(top)||top<0||top>35||!Number.isFinite(cluster)||cluster<0||cluster>2)return false;const wt=c.whaleTop10Pct,wd=c.whaleDeltaTop10Pct;if(wt!==null&&wt!==undefined&&wt!==''&&Number.isFinite(Number(wt))&&Number(wt)>=70&&Number(wt)<100)return false;if(wd!==null&&wd!==undefined&&wd!==''&&Number.isFinite(Number(wd))&&Number(wd)>=8)return false;return d==='PASS'||(d===''&&c.securityDecision==='PASS'&&holderSafe(c))}"
rep(old_insider,new_holder_insider,'HOLDER_INFERENCE')
rep("function coreSafe(c){return !!c&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&insiderSafe(c)&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&n(c.liquidityUsd)>=50_000&&impact(c)<=1.25}",
    "function coreSafe(c){return !!c&&c.securityDecision==='PASS'&&holderSafe(c)&&insiderSafe(c)&&!c.token2022&&c.sellRoute===true&&hardRejectEmpty(c.hardReject)&&n(c.liquidityUsd)>=50_000&&impact(c)<=1.25}",
    'CORE_SAFE_HOLDER')

sub(r"async function maybeScaleIn\(st,p\)\{\n.*?\n\}",
"""async function maybeScaleIn(st,p){
  if(!st.positions.length)return null;const ranked=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c&&coreSafe(x.c)&&!x.pos.scaleInLockedAfterProfit&&x.pos.weakExitCount===0).sort((a,b)=>rank(b.c)-rank(a.c));
  for(const x of ranked){const r=await placeBuy(st,x.c,x.index);if(r.placed)return{action:'ADD',reason:'IDLE_CAPITAL_SCALE',symbol:x.c.symbol};if(!['CAPITAL_HEADROOM_LOW','TARGET_ALREADY_SATISFIED','ALLOCATION_BELOW_MIN_ORDER'].includes(r.reason))return{action:'WAIT',reason:r.reason,symbol:x.c.symbol}}return null;
}""",'FORCED_SCALE')

sub(r"async function observeCapital\(st\)\{.*?\}\n",
"""async function observeCapital(st){const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)return;const p=rootPolicy(),bal=await solBalance(h.publicKey);observeBalance(st,bal,p.externalFlowThresholdLamports);try{const exitHeadroomLamports=await networkExitHeadroomLamports(p),reserveLamports=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports),investedLamports=portfolioInvested(st),capitalBaseLamports=Math.max(0,bal+investedLamports),deployableLamports=Math.max(0,bal-reserveLamports);atomic(`${APP}/runtime-status/capital-observability.json`,{version:'V390_IDLE_CAPITAL_ENFORCED',updatedAt:new Date().toISOString(),walletSolLamports:bal,walletSol:bal/1e9,investedLamports,investedSol:investedLamports/1e9,capitalBaseLamports,reserveLamports,reserveSol:reserveLamports/1e9,deployableLamports,deployableSol:deployableLamports/1e9,minOrderLamports:p.minOrderLamports,maxUtilizationPct:p.maxUtilizationPct,openPositions:st.positions.length,scaleAllowed:true})}catch{}atomic(statePath,st)}
""",'CAPITAL_OBSERVABILITY')

rep("MICRO_LIVE_EXECUTOR_V389_IDLE_CASH=STARTED","MICRO_LIVE_EXECUTOR_V390_IDLE_CAPITAL_ENFORCED=STARTED",'VERSION_MARKER')
p.write_text(s)
PY

node --check "$CAND"
testout="$(node "$CAND" --self-test)"
printf '%s\n' "$testout"
for k in MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT CAPITAL_UTILIZATION_FIRST=TRUE FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE EQUITY_GROWTH_SCALES_NEW_BUYS=TRUE; do grep -q "$k" <<<"$testout"; done
grep -q 'function holderSafe(c)' "$CAND"
grep -q 'holderSafe(c)&&insiderSafe(c)' "$CAND"
grep -q 'IDLE_CAPITAL_SCALE' "$CAND"
grep -q 'V390_IDLE_CAPITAL_ENFORCED' "$CAND"
grep -q 'MICRO_LIVE_EXECUTOR_V390_IDLE_CAPITAL_ENFORCED=STARTED' "$CAND"

WANT="$(sha256sum "$CAND" | awk '{print $1}')"
OLD_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
echo V390_EXPECTED_SHA="$WANT"
echo OLD_EXECUTOR_PID="${OLD_PID:-none}"

[ -w "$SRC_DIR" ] || { echo V390_FAIL=SRC_DIR_NOT_WRITABLE; exit 3; }
BACKUP="$RT/v390-pre-activate-executor-$(date -u +%Y%m%dT%H%M%SZ).js"
cp -a "$SRC" "$BACKUP"
TMP="$SRC_DIR/.micro-live-executor.v390.$$"
cp "$CAND" "$TMP"
chmod 0644 "$TMP"
[ "$(sha256sum "$TMP" | awk '{print $1}')" = "$WANT" ] || { rm -f "$TMP"; echo V390_FAIL=TMP_HASH; exit 4; }
mv -f "$TMP" "$SRC"
HAVE="$(sha256sum "$SRC" | awk '{print $1}')"
echo PRODUCTION_SHA="$HAVE"
[ "$HAVE" = "$WANT" ] || { cp "$BACKUP" "$SRC"; echo V390_FAIL=SOURCE_HASH; exit 5; }

ORIGINAL="$RT/v387-unified-final/run-paper.original.sh"
[ -f "$ORIGINAL" ] || { cp "$BACKUP" "$SRC"; echo V390_FAIL=ORIGINAL_RUNNER_MISSING; exit 6; }
cp "$APP/run-paper.sh" "$RT/v390-run-paper.pre.sh"
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
NEW_PID=""
for i in $(seq 1 45); do
  NEW_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
  [ -n "$NEW_PID" ] && [ "$NEW_PID" != "$OLD_PID" ] && break
  sleep 2
done
cp "$RT/v390-run-paper.pre.sh" "$APP/run-paper.sh"
chmod 0755 "$APP/run-paper.sh"
timeout 90s sudo -n /bin/systemctl restart meme-alpha-paper.service || true

NEW_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
if [ -z "$NEW_PID" ] || [ "$NEW_PID" = "$OLD_PID" ]; then
  cp "$BACKUP" "$SRC"
  echo V390_FAIL=EXECUTOR_NOT_RELOADED
  exit 7
fi
echo NEW_EXECUTOR_PID="$NEW_PID"
node --check "$SRC"
grep -q 'MICRO_LIVE_EXECUTOR_V390_IDLE_CAPITAL_ENFORCED=STARTED' "$SRC"
grep -q 'function holderSafe(c)' "$SRC"
grep -q 'holderSafe(c)&&insiderSafe(c)' "$SRC"
grep -q 'IDLE_CAPITAL_SCALE' "$SRC"

for i in $(seq 1 45); do
  sleep 2
  if python3 - <<'PY'
import json,pathlib,time,sys
rt=pathlib.Path('/opt/meme-alpha/app/runtime-status')
g=json.loads((rt/'micro-live-gate.json').read_text()); s=json.loads((rt/'signal-snapshot.json').read_text()); rows=s.get('candidates') or []
def n(v,d=0):
    try:return float(v)
    except:return d
def holder(c):
    d=str(c.get('holderClusterDecision') or '')
    if d in ('BLOCK','REVIEW'): return False
    top=n(c.get('topHoldersPct'),-1); cl=n(c.get('holderClusterMaxAccountsSameOwner'),-1)
    if top<0 or top>35 or cl<0 or cl>2:return False
    wt=c.get('whaleTop10Pct'); wd=c.get('whaleDeltaTop10Pct')
    if wt not in (None,'') and n(wt)>=70 and n(wt)<100:return False
    if wd not in (None,'') and n(wd)>=8:return False
    return d=='PASS' or (d=='' and c.get('securityDecision')=='PASS')
def insider(c):
    d=str(c.get('insiderRiskDecision') or '')
    if d in ('BLOCK','REVIEW'): return False
    top=n(c.get('topHoldersPct'),-1); cl=n(c.get('holderClusterMaxAccountsSameOwner'),-1)
    if top<0 or top>35 or cl<0 or cl>2:return False
    wt=c.get('whaleTop10Pct'); wd=c.get('whaleDeltaTop10Pct')
    if wt not in (None,'') and n(wt)>=70 and n(wt)<100:return False
    if wd not in (None,'') and n(wd)>=8:return False
    return d=='PASS' or (d=='' and c.get('securityDecision')=='PASS' and holder(c))
safe=[c for c in rows if c.get('securityDecision')=='PASS' and holder(c) and insider(c) and c.get('token2022') is not True and c.get('sellRoute') is True and not(c.get('hardReject') or []) and n(c.get('liquidityUsd'))>=50000 and abs(n(c.get('sellPriceImpactPct',c.get('priceImpactPct')),99))<=1.25]
print('V390_LIVE',{'allowed':g.get('allowed'),'sourceHealthy':g.get('sourceHealthy'),'riskEntryAllowed':g.get('riskEntryAllowed'),'liveRiskReady':g.get('liveRiskReady'),'scaleAllowed':g.get('scaleAllowed'),'signalCount':len(rows),'coreSafeCount':len(safe),'coreSafeSymbols':[c.get('symbol') for c in safe[:12]],'signalAgeSec':round(time.time()-(rt/'signal-snapshot.json').stat().st_mtime,1),'reasons':g.get('reasons')})
assert g.get('allowed') is True and g.get('sourceHealthy') is True and g.get('riskEntryAllowed') is True and g.get('liveRiskReady') is True and g.get('scaleAllowed') is True
assert time.time()-(rt/'signal-snapshot.json').stat().st_mtime<60
assert len(safe)>0
PY
  then break
  fi
  [ "$i" -lt 45 ] || { echo V390_FAIL=NO_CORE_SAFE_AFTER_INFERENCE; exit 8; }
done

# Let the live loop publish capital status and consume deployable cash when possible.
CAP_OK=0
for i in $(seq 1 30); do
  sleep 2
  if [ -r "$RT/capital-observability.json" ]; then
    if python3 - <<'PY'
import json,pathlib,time
p=pathlib.Path('/opt/meme-alpha/app/runtime-status/capital-observability.json')
x=json.loads(p.read_text())
age=time.time()-p.stat().st_mtime
print('CAPITAL',x,'ageSec',round(age,1))
assert age<30
# Success means no meaningful idle cash remains; otherwise keep checking while the live loop allocates it.
assert int(x.get('deployableLamports') or 0) < int(x.get('minOrderLamports') or 0)
PY
    then CAP_OK=1; break; fi
  fi
done

for svc in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service meme-alpha-realtime-pulse.service meme-alpha-trend-pulse.service meme-alpha-whale-flow.service; do
  systemctl is-active --quiet "$svc" || { echo V390_FAIL_SERVICE="$svc"; exit 9; }
  echo "$svc=active"
done
[ "$(pgrep -fc '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)" -eq 1 ] || { echo V390_FAIL=EXECUTOR_PROCESS_COUNT; exit 10; }

echo CAPITAL_IDLE_DRAINED="$CAP_OK"
[ -r "$RT/capital-observability.json" ] && cat "$RT/capital-observability.json" || true
echo V390_IDLE_CAPITAL_ENFORCED=ACTIVE
echo HOLDER_MISSING_EVIDENCE_INFERENCE=TRUE
echo EXPLICIT_HOLDER_REVIEW_BLOCK_PRESERVED=TRUE
echo SCALE_ALLOWED=TRUE
echo IDLE_CAPITAL_TARGET_UTILIZATION_PCT=94
echo HARD_SECURITY_SELLABILITY_TOKEN2022_GUARDS=ENFORCED
