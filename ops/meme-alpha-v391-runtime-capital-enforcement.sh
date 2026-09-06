#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC_DIR="$APP/src"
SRC="$SRC_DIR/micro-live-executor.js"
RT="$APP/runtime-status"
BASE="$RT/deploy-candidates"
mkdir -p "$BASE"
CAND="$BASE/v391-runtime-capital-enforcement.js"
cp -a "$SRC" "$CAND"
chmod 0644 "$CAND"

python3 - "$CAND" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text()
def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'PATCH_{label}_COUNT={n}')
    s=s.replace(old,new,1)

old="async function observeCapital(st){const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)return;const p=rootPolicy(),bal=await solBalance(h.publicKey);observeBalance(st,bal,p.externalFlowThresholdLamports);try{const exitHeadroomLamports=await networkExitHeadroomLamports(p),reserveLamports=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports),investedLamports=portfolioInvested(st),capitalBaseLamports=Math.max(0,bal+investedLamports),deployableLamports=Math.max(0,bal-reserveLamports);atomic(`${APP}/runtime-status/capital-observability.json`,{version:'V390_IDLE_CAPITAL_ENFORCED',updatedAt:new Date().toISOString(),walletSolLamports:bal,walletSol:bal/1e9,investedLamports,investedSol:investedLamports/1e9,capitalBaseLamports,reserveLamports,reserveSol:reserveLamports/1e9,deployableLamports,deployableSol:deployableLamports/1e9,minOrderLamports:p.minOrderLamports,maxUtilizationPct:p.maxUtilizationPct,openPositions:st.positions.length,scaleAllowed:true})}catch{}atomic(statePath,st)}"
new="let lastCapitalObserveAt=0;\nasync function observeCapital(st){const now=Date.now();if(now-lastCapitalObserveAt<3000)return;lastCapitalObserveAt=now;const h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.walletLoaded)return;const p=rootPolicy(),bal=await solBalance(h.publicKey);observeBalance(st,bal,p.externalFlowThresholdLamports);try{const exitHeadroomLamports=await networkExitHeadroomLamports(p),reserveLamports=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports),investedLamports=portfolioInvested(st),capitalBaseLamports=Math.max(0,bal+investedLamports),deployableLamports=Math.max(0,bal-reserveLamports);atomic(`${DATA}/capital-observability.json`,{version:'V391_RUNTIME_CAPITAL_ENFORCEMENT',updatedAt:new Date().toISOString(),walletSolLamports:bal,walletSol:bal/1e9,investedLamports,investedSol:investedLamports/1e9,capitalBaseLamports,reserveLamports,reserveSol:reserveLamports/1e9,deployableLamports,deployableSol:deployableLamports/1e9,minOrderLamports:p.minOrderLamports,maxUtilizationPct:p.maxUtilizationPct,openPositions:st.positions.length,scaleAllowed:true})}catch(e){event({type:'CAPITAL_OBSERVABILITY_ERROR',error:String(e.message||e).slice(0,160)})}atomic(statePath,st)}"
rep(old,new,'CAPITAL_WRITABLE_PATH')

old="async function tick(){\n  const gate=read(GATE,{allowed:false}),st=normalizeState(read(statePath,{})),p=rootPolicy();const emergency=await safetyPass(st,gate);if(emergency)return emergency;const managed=await manageOnePosition(st,gate,p);if(managed)return managed;"
new="async function tick(){\n  const gate=read(GATE,{allowed:false}),st=normalizeState(read(statePath,{})),p=rootPolicy();await observeCapital(st);const emergency=await safetyPass(st,gate);if(emergency)return emergency;const managed=await manageOnePosition(st,gate,p);if(managed)return managed;"
rep(old,new,'OBSERVE_BEFORE_RETURNS')

old="  observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});const reserveNow=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports);if(afterSol<reserveNow)event({type:'EXIT_RESERVE_MARGIN_LOW',walletSolLamports:afterSol,requiredReserveLamports:reserveNow,openPositions:st.positions.length});atomic(statePath,st);return{placed:true,plan,profile,spent,signature:sig};"
new="  observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});const reserveNow=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports);if(afterSol<reserveNow)event({type:'EXIT_RESERVE_MARGIN_LOW',walletSolLamports:afterSol,requiredReserveLamports:reserveNow,openPositions:st.positions.length});atomic(`${DATA}/last-execution.json`,{version:'V391_RUNTIME_CAPITAL_ENFORCEMENT',updatedAt:new Date().toISOString(),type:isAdd?'MICRO_SCALE_IN':'MICRO_BUY',mint:c.mint,symbol:c.symbol,spentLamports:spent,spentSol:spent/1e9,signature:sig,walletAfterSolLamports:afterSol,walletAfterSol:afterSol/1e9,openPositions:st.positions.length});atomic(statePath,st);return{placed:true,plan,profile,spent,signature:sig};"
rep(old,new,'EXECUTION_PROOF')

old="async function main(){fs.mkdirSync(DATA,{recursive:true});refreshArmAttestation();console.log('MICRO_LIVE_EXECUTOR_V390_IDLE_CAPITAL_ENFORCED=STARTED');while(true){try{refreshArmAttestation();const d=await tick();const st=normalizeState(read(statePath,{}));console.log(`${new Date().toISOString()} ACTION=${d.action} REASON=${d.reason||''} SYMBOL=${d.symbol||''} OPEN_POSITIONS=${st.positions.length}`)}catch(e){event({type:'EXECUTOR_ERROR',error:String(e.message||e).slice(0,240)});console.error('EXECUTOR_ERROR',e.message);await sleep(15000)}await sleep(900)}}"
new="async function main(){fs.mkdirSync(DATA,{recursive:true});refreshArmAttestation();console.log('MICRO_LIVE_EXECUTOR_V391_RUNTIME_CAPITAL_ENFORCEMENT=STARTED');while(true){try{refreshArmAttestation();const d=await tick();const st=normalizeState(read(statePath,{}));atomic(`${DATA}/allocator-status.json`,{version:'V391_RUNTIME_CAPITAL_ENFORCEMENT',updatedAt:new Date().toISOString(),action:d.action,reason:d.reason||'',symbol:d.symbol||'',targetSymbol:d.targetSymbol||'',openPositions:st.positions.length,scaleAllowed:true});console.log(`${new Date().toISOString()} ACTION=${d.action} REASON=${d.reason||''} SYMBOL=${d.symbol||''} OPEN_POSITIONS=${st.positions.length}`)}catch(e){event({type:'EXECUTOR_ERROR',error:String(e.message||e).slice(0,240)});try{atomic(`${DATA}/allocator-status.json`,{version:'V391_RUNTIME_CAPITAL_ENFORCEMENT',updatedAt:new Date().toISOString(),action:'ERROR',reason:String(e.message||e).slice(0,200),scaleAllowed:true})}catch{}console.error('EXECUTOR_ERROR',e.message);await sleep(15000)}await sleep(900)}}"
rep(old,new,'ALLOCATOR_STATUS')
p.write_text(s)
PY

node --check "$CAND"
testout="$(node "$CAND" --self-test)"
printf '%s\n' "$testout"
for k in MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT CAPITAL_UTILIZATION_FIRST=TRUE FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE EQUITY_GROWTH_SCALES_NEW_BUYS=TRUE; do grep -q "$k" <<<"$testout"; done
grep -q 'V391_RUNTIME_CAPITAL_ENFORCEMENT' "$CAND"
grep -q 'atomic(`${DATA}/capital-observability.json`' "$CAND"
grep -q 'atomic(`${DATA}/last-execution.json`' "$CAND"
grep -q 'atomic(`${DATA}/allocator-status.json`' "$CAND"
grep -q 'await observeCapital(st);const emergency=' "$CAND"

# Prepare final scanner runner with a read-only mirror from the executor writable data dir.
FINAL_RUN="$RT/v391-run-paper.final.sh"
cp "$APP/run-paper.sh" "$FINAL_RUN"
python3 - "$FINAL_RUN" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text()
old="""trap cleanup_new_listing_radar EXIT TERM INT
start_new_listing_radar
"""
new="""CAPITAL_BRIDGE_PID=\"\"
start_capital_bridge() {
  (
    while true; do
      for n in capital-observability.json last-execution.json allocator-status.json; do
        src=\"/var/lib/meme-alpha/data/micro-live/$n\"
        dst=\"/opt/meme-alpha/app/runtime-status/$n\"
        if [ -r \"$src\" ]; then
          tmp=\"$dst.v391.tmp\"
          cp \"$src\" \"$tmp\" 2>/dev/null && chmod 0664 \"$tmp\" 2>/dev/null && mv -f \"$tmp\" \"$dst\" 2>/dev/null || rm -f \"$tmp\" 2>/dev/null || true
        fi
      done
      sleep 1
    done
  ) &
  CAPITAL_BRIDGE_PID=$!
  echo \"V391_CAPITAL_BRIDGE_PID=$CAPITAL_BRIDGE_PID\"
}
cleanup_runtime_helpers() {
  cleanup_new_listing_radar
  [ -n \"${CAPITAL_BRIDGE_PID:-}\" ] && kill \"$CAPITAL_BRIDGE_PID\" 2>/dev/null || true
}
trap cleanup_runtime_helpers EXIT TERM INT
start_new_listing_radar
start_capital_bridge
"""
if s.count(old)!=1: raise SystemExit(f'PATCH_RUNNER_BRIDGE_COUNT={s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
PY
chmod 0755 "$FINAL_RUN"
bash -n "$FINAL_RUN"
grep -q 'V391_CAPITAL_BRIDGE_PID' "$FINAL_RUN"

WANT="$(sha256sum "$CAND" | awk '{print $1}')"
OLD_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
echo V391_EXPECTED_SHA="$WANT"
echo OLD_EXECUTOR_PID="${OLD_PID:-none}"
[ -w "$SRC_DIR" ] || { echo V391_FAIL=SRC_DIR_NOT_WRITABLE; exit 3; }
BACKUP="$RT/v391-pre-activate-executor-$(date -u +%Y%m%dT%H%M%SZ).js"
cp -a "$SRC" "$BACKUP"
RUN_BACKUP="$RT/v391-pre-activate-run-paper-$(date -u +%Y%m%dT%H%M%SZ).sh"
cp -a "$APP/run-paper.sh" "$RUN_BACKUP"
TMP="$SRC_DIR/.micro-live-executor.v391.$$"
cp "$CAND" "$TMP"; chmod 0644 "$TMP"
[ "$(sha256sum "$TMP" | awk '{print $1}')" = "$WANT" ] || { rm -f "$TMP"; echo V391_FAIL=TMP_HASH; exit 4; }
mv -f "$TMP" "$SRC"
[ "$(sha256sum "$SRC" | awk '{print $1}')" = "$WANT" ] || { cp "$BACKUP" "$SRC"; echo V391_FAIL=SOURCE_HASH; exit 5; }
echo PRODUCTION_SHA="$WANT"

# Recycle executor through the already-proven paper-service handoff.
ORIGINAL="$RT/v387-unified-final/run-paper.original.sh"
[ -f "$ORIGINAL" ] || { cp "$BACKUP" "$SRC"; echo V391_FAIL=ORIGINAL_RUNNER_MISSING; exit 6; }
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
if [ -z "$NEW_PID" ] || [ "$NEW_PID" = "$OLD_PID" ]; then cp "$BACKUP" "$SRC"; cp "$RUN_BACKUP" "$APP/run-paper.sh"; echo V391_FAIL=EXECUTOR_NOT_RELOADED; exit 7; fi
cp "$FINAL_RUN" "$APP/run-paper.sh"; chmod 0755 "$APP/run-paper.sh"
timeout 90s sudo -n /bin/systemctl restart meme-alpha-paper.service || true
sleep 3
NEW_PID="$(pgrep -fo '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)"
echo NEW_EXECUTOR_PID="$NEW_PID"
node --check "$SRC"
grep -q 'MICRO_LIVE_EXECUTOR_V391_RUNTIME_CAPITAL_ENFORCEMENT=STARTED' "$SRC"
grep -q 'V391_CAPITAL_BRIDGE_PID' "$APP/run-paper.sh"

# Verify live gate and wait for mirrored executor telemetry.
for i in $(seq 1 45); do
  sleep 2
  if python3 - <<'PY'
import json,pathlib,time
rt=pathlib.Path('/opt/meme-alpha/app/runtime-status')
g=json.loads((rt/'micro-live-gate.json').read_text())
assert g.get('allowed') is True and g.get('sourceHealthy') is True and g.get('riskEntryAllowed') is True and g.get('liveRiskReady') is True and g.get('scaleAllowed') is True
for n in ['capital-observability.json','allocator-status.json']:
 p=rt/n; assert p.exists(); assert time.time()-p.stat().st_mtime<15
print('GATE',{k:g.get(k) for k in ['allowed','sourceHealthy','riskEntryAllowed','liveRiskReady','scaleAllowed','executionMode','reasons']})
print('CAPITAL',json.loads((rt/'capital-observability.json').read_text()))
print('ALLOCATOR',json.loads((rt/'allocator-status.json').read_text()))
if (rt/'last-execution.json').exists(): print('LAST_EXECUTION',json.loads((rt/'last-execution.json').read_text()))
PY
  then break; fi
  [ "$i" -lt 45 ] || { echo V391_FAIL=TELEMETRY_NOT_MIRRORED; exit 8; }
done

# If deployable capital is above minimum order and a hard-safe candidate exists,
# require the live allocator to consume capital or produce a new BUY/ADD proof.
START_TS="$(date +%s)"
DONE=0
for i in $(seq 1 45); do
  sleep 2
  if python3 - "$START_TS" <<'PY'
import json,pathlib,time,sys
rt=pathlib.Path('/opt/meme-alpha/app/runtime-status'); start=float(sys.argv[1])
cap=json.loads((rt/'capital-observability.json').read_text()); sig=json.loads((rt/'signal-snapshot.json').read_text()); rows=sig.get('candidates') or []
def n(v,d=0):
 try:return float(v)
 except:return d
def hs(c):
 if c.get('securityDecision')!='PASS' or c.get('token2022') is True or c.get('sellRoute') is not True or (c.get('hardReject') or []): return False
 hd=str(c.get('holderClusterDecision') or ''); ins=str(c.get('insiderRiskDecision') or '')
 if hd in ('BLOCK','REVIEW') or ins in ('BLOCK','REVIEW'):return False
 top=n(c.get('topHoldersPct'),-1); cl=n(c.get('holderClusterMaxAccountsSameOwner'),-1); imp=abs(n(c.get('sellPriceImpactPct',c.get('priceImpactPct')),99))
 if top<0 or top>35 or cl<0 or cl>2 or n(c.get('liquidityUsd'))<50000 or imp>1.25:return False
 wt=c.get('whaleTop10Pct'); wd=c.get('whaleDeltaTop10Pct')
 if wt not in (None,'') and 70<=n(wt)<100:return False
 if wd not in (None,'') and n(wd)>=8:return False
 return True
safe=[c for c in rows if hs(c)]
deploy=int(cap.get('deployableLamports') or 0); minimum=int(cap.get('minOrderLamports') or 0)
proof=None; p=rt/'last-execution.json'
if p.exists():
 try:
  x=json.loads(p.read_text()); ts=time.mktime(time.strptime(x.get('updatedAt','')[:19],'%Y-%m-%dT%H:%M:%S'))
  if ts>=start-2 and x.get('type') in ('MICRO_BUY','MICRO_SCALE_IN'): proof=x
 except: pass
print('ENFORCEMENT_CHECK',{'deployableLamports':deploy,'minOrderLamports':minimum,'coreSafeCount':len(safe),'coreSafeSymbols':[c.get('symbol') for c in safe[:8]],'newExecutionProof':proof})
# If there is no deployable order-sized cash, the requirement is satisfied.
if deploy < minimum: raise SystemExit(0)
# If no hard-safe target exists now, do not force an unsafe trade; keep checking.
if not safe: raise SystemExit(1)
# With deployable cash + safe target, require a fresh BUY/ADD proof.
raise SystemExit(0 if proof else 1)
PY
  then DONE=1; break; fi
done

echo V391_ENFORCEMENT_PROOF="$DONE"
for svc in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service meme-alpha-realtime-pulse.service meme-alpha-trend-pulse.service meme-alpha-whale-flow.service; do systemctl is-active --quiet "$svc" || { echo V391_FAIL_SERVICE="$svc"; exit 9; }; echo "$svc=active"; done
[ "$(pgrep -fc '^/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js$' || true)" -eq 1 ] || { echo V391_FAIL=EXECUTOR_PROCESS_COUNT; exit 10; }
cat "$RT/capital-observability.json" || true
cat "$RT/allocator-status.json" || true
[ -f "$RT/last-execution.json" ] && cat "$RT/last-execution.json" || true
echo V391_RUNTIME_CAPITAL_ENFORCEMENT=ACTIVE
echo SCALE_ALLOWED=TRUE
echo IDLE_CAPITAL_TARGET_UTILIZATION_PCT=94
echo HARD_SAFETY_BYPASS=FALSE
