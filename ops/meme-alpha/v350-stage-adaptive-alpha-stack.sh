#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
APP=/opt/meme-alpha/app
STAGE="$APP/runtime-status/v350-stage"
OUT="$STAGE/micro-live-executor-v350-adaptive-alpha.js"
RADAR="$STAGE/new-listing-radar-v350.js"
mkdir -p "$STAGE"
cp "$APP/src/micro-live-executor.js" "$OUT"
cp "$APP/src/new-listing-radar.js" "$RADAR"
cp "$ROOT/ops/meme-alpha/v350-realtime-pool-pulse.js" "$STAGE/realtime-pool-pulse.js"
cp "$ROOT/ops/meme-alpha/v350-whale-flow-intel.js" "$STAGE/whale-flow-intel.js"
python3 - "$OUT" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
def sub(pattern,repl,count=1):
    global s
    s2,n=re.subn(pattern,repl,s,count=count,flags=re.S)
    if n!=count: raise SystemExit(f'PATCH_MISS {pattern[:100]!r} got={n}')
    s=s2
if '3.42.0-capital-utilization' not in s or 'CAPITAL_UTILIZATION_FIRST' not in s:
    raise SystemExit('V342_BASELINE_REQUIRED')
s=s.replace("const TREND=`${APP}/runtime-status/trend-pulse.json`;","const TREND=`${APP}/runtime-status/trend-pulse.json`;\nconst REALTIME=`${APP}/runtime-status/realtime-pool-pulse.json`;\nconst WHALE=`${APP}/runtime-status/whale-flow-intel.json`;",1)
s=s.replace("function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||null}","function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||(typeof j?.result==='string'?j.result:null)||null}",1)
sub(r"async function executeOrder\(o\)\{.*?\n\}","""async function executeOrder(o){
  const cfg=read(`${APP}/config/runtime.json`),started=Date.now(),tx=o?.signedTransaction;
  if(typeof tx==='string'&&tx.length>200){
    const endpoints=['https://singapore.mainnet.block-engine.jito.wtf/api/v1/transactions','https://tokyo.mainnet.block-engine.jito.wtf/api/v1/transactions'];
    try{
      const landed=await Promise.any(endpoints.map(async url=>{const t=Date.now(),j=await post(url,{jsonrpc:'2.0',id:1,method:'sendTransaction',params:[tx,{encoding:'base64'}]});const sig=signature(j);if(!sig)throw new Error('JITO_NO_SIGNATURE');return{sig,url,submitMs:Date.now()-t}}));
      const confirmStart=Date.now();await confirm(landed.sig);event({type:'EXECUTION_FEEDBACK',route:'JITO_REGION_RACE',endpoint:landed.url,submitMs:landed.submitMs,confirmMs:Date.now()-confirmStart,totalMs:Date.now()-started,signature:landed.sig});return landed.sig;
    }catch(e){event({type:'EXECUTION_ROUTE_FALLBACK',from:'JITO_REGION_RACE',to:'JUPITER_EXECUTE',error:String(e?.message||e).slice(0,160)})}
  }
  const t=Date.now(),j=await post(`${String(cfg.jupiter).replace(/\\/$/,'')}/swap/v2/execute`,{signedTransaction:o.signedTransaction,requestId:o.requestId}),sig=signature(j);if(!sig)throw new Error('EXECUTE_NO_SIGNATURE');const submitMs=Date.now()-t,confirmStart=Date.now();await confirm(sig);event({type:'EXECUTION_FEEDBACK',route:'JUPITER_EXECUTE',submitMs,confirmMs:Date.now()-confirmStart,totalMs:Date.now()-started,signature:sig});return sig;
}""")
s=s.replace("for(let i=0;i<30;i++){const r=await rpc('getSignatureStatuses'","for(let i=0;i<60;i++){const r=await rpc('getSignatureStatuses'",1)
s=s.replace("await sleep(1000)}throw new Error('CHAIN_CONFIRM_TIMEOUT')","await sleep(400)}throw new Error('CHAIN_CONFIRM_TIMEOUT')",1)
helper="""
function intelRow(path,c,maxAgeSec=20){if(!c)return null;const x=read(path,{}),age=(Date.now()-Date.parse(x.updatedAt||0))/1000;if(!Number.isFinite(age)||age<0||age>maxAgeSec||x.status==='DEGRADED')return null;return (x.rows||[]).find(r=>r.mint===c.mint)||null}
function realtimeFor(c){return intelRow(REALTIME,c,8)}
function whaleFor(c){return intelRow(WHALE,c,45)}
function learningState(st){if(!st.learning||typeof st.learning!=='object')st.learning={version:1,totalClosed:0,totalWins:0,meanReturnPct:0,buckets:{}};if(!st.learning.buckets)st.learning.buckets={};return st.learning}
function featureKeys(c){const p=pulseFor(c),keys=[];keys.push(n(c.score)>=78?'SCORE_HIGH':n(c.score)>=68?'SCORE_MID':'SCORE_LOW');keys.push(n(c.liquidityUsd)>=500000?'LIQ_HIGH':n(c.liquidityUsd)>=150000?'LIQ_MID':'LIQ_LOW');keys.push(n(c.netBuyers5m)>=10?'FLOW_HIGH':n(c.netBuyers5m)>=3?'FLOW_MID':'FLOW_LOW');keys.push(n(p?.pulseScore)>=70?'PULSE_HIGH':n(p?.pulseScore)>=55?'PULSE_MID':'PULSE_LOW');keys.push(impact(c)<=.5?'IMPACT_LOW':impact(c)<=.9?'IMPACT_MID':'IMPACT_HIGH');const rt=realtimeFor(c);if(rt)keys.push(n(rt.eventMomentum)>=1.5&&n(rt.events5s)>=3?'RT_ACCEL':'RT_NORMAL');const w=whaleFor(c);if(w)keys.push(n(w.whaleFlowScore)>=2?'WHALE_HEALTHY':n(w.whaleFlowScore)<=-3?'WHALE_RISK':'WHALE_NEUTRAL');return keys}
function learnedBoost(st,c){const L=learningState(st),vals=[];for(const k of featureKeys(c)){const b=L.buckets[k];if(!b||n(b.count)<1)continue;const shrink=n(b.count)/(n(b.count)+18),m=clamp(n(b.meanReturnPct),-40,80);vals.push(m*shrink)}if(!vals.length)return 0;return clamp(vals.reduce((a,b)=>a+b,0)/vals.length/4,-8,12)}
function captureEntryFeatures(c,profile={}){return{keys:featureKeys(c),score:n(c.score),opportunityScore:opportunityScore(c),liquidityUsd:n(c.liquidityUsd),netBuyers5m:n(c.netBuyers5m),impactPct:impact(c),allocationPct:n(profile.pct),capturedAt:new Date().toISOString()}}
function learnClosedTrade(st,pos){const life=Math.max(1,n(pos.lifetimeCostLamports,n(pos.costBasisLamports))),pnl=n(pos.realizedPnlLamports),ret=clamp(pnl/life*100,-95,300),L=learningState(st);L.totalClosed=n(L.totalClosed)+1;L.totalWins=n(L.totalWins)+(ret>0?1:0);L.meanReturnPct+=(ret-n(L.meanReturnPct))/L.totalClosed;for(const k of pos.entryFeatures?.keys||[]){const b=L.buckets[k]||(L.buckets[k]={count:0,wins:0,meanReturnPct:0});b.count=n(b.count)+1;b.wins=n(b.wins)+(ret>0?1:0);b.meanReturnPct+=(ret-n(b.meanReturnPct))/b.count}event({type:'ONLINE_LEARNING_UPDATE',mint:pos.mint,symbol:pos.symbol,returnPct:ret,totalClosed:L.totalClosed,winRate:L.totalClosed?L.totalWins/L.totalClosed:0})}
function expectedEdge(st,c){return opportunityScore(c)+learnedBoost(st,c)}
"""
s=s.replace("function opportunityScore(c){",helper+"\nfunction opportunityScore(c){",1)
sub(r"function opportunityScore\(c\)\{.*?\}\nfunction opportunityLane", """function opportunityScore(c){const base=n(c.score),p=pulseFor(c);let add=0;if(p){if(n(p.volumeAcceleration)>=1.45)add+=4;else if(n(p.volumeAcceleration)>=1.10)add+=2;if(n(p.txnAcceleration)>=1.30)add+=3;else if(n(p.txnAcceleration)>=1.05)add+=1;if(n(p.buySellRatio)>=1.25)add+=2;if(themeStrength(c)>=60)add+=2;if(n(p.pulseScore)>=70)add+=1;if(p.status==='EXHAUSTED')add-=8;if(p.promotionFlag===true&&n(p.pulseScore)<65)add-=3}const rt=realtimeFor(c);if(rt&&n(rt.lastEventAgeMs,99999)<=2500){if(n(rt.eventMomentum)>=1.8&&n(rt.events5s)>=3)add+=5;else if(n(rt.events5s)>=2)add+=2}const w=whaleFor(c);if(w)add+=clamp(n(w.whaleFlowScore),-6,4);return clamp(base+add,base-10,base+18)}
function opportunityLane""")
sub(r"function allocationProfile\(c,p,st,capitalBaseLamports\)\{.*?\n\}\nfunction rank", """function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const rt=realtimeFor(c),rtQ=rt?clamp((n(rt.eventMomentum)-.8)/2.2,0,1):.35,w=whaleFor(c),whaleQ=w?clamp((n(w.whaleFlowScore)+10)/16,0,1):.50,learn=learnedBoost(st,c),learnQ=clamp(.5+learn/24,0,1);
  const quality=clamp(scoreQ*.26+netQ*.15+avgQ*.09+liqQ*.13+impactQ*.13+pulseQ*.08+rtQ*.07+whaleQ*.05+learnQ*.04,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.28),.80,2.00);
  const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1),basePct=4+31*Math.pow(quality,1.20),cashBoost=1+0.38*freeRatio,pct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct);
  return{name:'AUTO_ALPHA',pct,quality,growth,exposure,freeRatio,cashBoost,learnedBoost:learn,expectedEdge:expectedEdge(st,c),score:opportunityScore(c)};
}
function rank""")
sub(r"function rank\(c\)\{.*?\}\nfunction bestCandidate\(p,held\)\{.*?\}","""function rank(c){const rt=realtimeFor(c),w=whaleFor(c);return opportunityScore(c)*100+n(c.netBuyers5m)*2+n(c.avgNetBuyersLast2)+n(c.organicRatio5m)*30+n(rt?.eventMomentum)*16+n(w?.whaleFlowScore)*8-Math.max(0,n(c.priceChange5m)-10)*10}
function bestCandidate(p,held,st){return candidates().filter(c=>!held.has(c.mint)&&trendEntryEligible(c)).sort((a,b)=>expectedEdge(st,b)-expectedEdge(st,a)||rank(b)-rank(a))[0]||null}""")
s=s.replace("pos.tp1Done=pos.tp1Done===true;pos.tp2Done=pos.tp2Done===true;pos.tp3Done=pos.tp3Done===true;pos.profitProtectDone=pos.profitProtectDone===true;pos.scaleInLockedAfterProfit=pos.scaleInLockedAfterProfit===true;\n  return pos;","pos.tp1Done=pos.tp1Done===true;pos.tp2Done=pos.tp2Done===true;pos.tp3Done=pos.tp3Done===true;pos.profitProtectDone=pos.profitProtectDone===true;pos.scaleInLockedAfterProfit=pos.scaleInLockedAfterProfit===true;\n  if(!Number.isFinite(Number(pos.lifetimeCostLamports)))pos.lifetimeCostLamports=n(pos.costBasisLamports);if(!Number.isFinite(Number(pos.realizedPnlLamports)))pos.realizedPnlLamports=0;\n  return pos;",1)
s=s.replace("pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;","pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;pos.lifetimeCostLamports=n(pos.lifetimeCostLamports)+spent;",1)
s=s.replace("st.positions.push(pos);event({type:'MICRO_BUY'","pos.entryFeatures=captureEntryFeatures(c,profile);pos.lifetimeCostLamports=spent;pos.realizedPnlLamports=0;st.positions.push(pos);event({type:'MICRO_BUY'",1)
old="const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){st.closed=n(st.closed)+1;st.positions.splice(index,1)}else{"
new="pos.realizedPnlLamports=n(pos.realizedPnlLamports)+pnl;const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){learnClosedTrade(st,pos);st.closed=n(st.closed)+1;st.positions.splice(index,1)}else{"
if old not in s: raise SystemExit('SELL_LEARNING_PATCH_MISS')
s=s.replace(old,new,1)
sub(r"function rotationSource\(st,newC\)\{.*?\}\nasync function maybeRotate", """function rotationSource(st,newC){const ns=expectedEdge(st,newC),newImpact=impact(newC),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:expectedEdge(st,x.c),weak:softTrendWeak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);for(const x of rows){const switchingCost=(newImpact+Math.max(0,n(x.pos.lastPreviewImpactPct,impact(x.c))))*1.5,advantage=ns-x.oldScore-switchingCost;if(x.weak||advantage>=13){if(n(x.pos.lastReturnPct)>20&&!x.weak&&advantage<22)continue;return{...x,advantage,switchingCost}}}return null}
async function maybeRotate""")
s=s.replace("c=bestCandidate(p,held);","c=bestCandidate(p,held,st);",1)
s=s.replace("now-last<10_000","now-last<5_000",1)
s=s.replace("st.version='3.42.0-capital-utilization'","st.version='3.50.0-adaptive-alpha'",1)
s=s.replace("MICRO_LIVE_EXECUTOR_V342_CAPITAL_UTILIZATION=STARTED","MICRO_LIVE_EXECUTOR_V350_ADAPTIVE_ALPHA=STARTED",1)
s=s.replace("MICRO_EXECUTOR_V342_CAPITAL_UTILIZATION_SELF_TEST=PASS","MICRO_EXECUTOR_V350_ADAPTIVE_ALPHA_SELF_TEST=PASS",1)
s=s.replace("await sleep(4000)","await sleep(1500)",1)
marker="console.log('NETWORK_EXECUTION=NOT_CALLED');"
if marker not in s: raise SystemExit('SELFTEST_MARKER_MISS')
s=s.replace(marker,"console.log('REALTIME_POOL_PULSE_INTEGRATION=TRUE');console.log('ONCHAIN_WHALE_FLOW_INTEGRATION=TRUE');console.log('ONLINE_EXPECTANCY_LEARNING=TRUE');console.log('OPPORTUNITY_COST_ROTATION=TRUE');console.log('JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE');console.log('EXECUTION_FEEDBACK_LOOP=TRUE');console.log('ADAPTIVE_FAST_LOOP_MS=1500');"+marker,1)
p.write_text(s)
PY
python3 - "$RADAR" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();s=s.replace("const MAX_MINTS=60;","const MAX_MINTS=90;",1);s=s.replace("version:'3.18.0'","version:'3.50.0'",1);p.write_text(s)
PY
/usr/bin/node --check "$OUT"
/usr/bin/node --check "$RADAR"
/usr/bin/node --check "$STAGE/realtime-pool-pulse.js"
/usr/bin/node --check "$STAGE/whale-flow-intel.js"
TEST=$(/usr/bin/node "$OUT" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'MICRO_EXECUTOR_V350_ADAPTIVE_ALPHA_SELF_TEST=PASS'
echo "$TEST" | grep -q 'ONLINE_EXPECTANCY_LEARNING=TRUE'
echo "$TEST" | grep -q 'JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE'
/usr/bin/node "$STAGE/realtime-pool-pulse.js" --self-test | grep -q 'V350_REALTIME_POOL_PULSE_SELF_TEST=PASS'
/usr/bin/node "$STAGE/whale-flow-intel.js" --self-test | grep -q 'V350_WHALE_FLOW_SELF_TEST=PASS'
sha256sum "$OUT" | tee "$STAGE/executor.sha256"
cat > "$STAGE/install-v350.sh" <<'ROOT'
#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V350_INSTALL_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app; STAGE="$APP/runtime-status/v350-stage"; DST="$APP/src/micro-live-executor.js"; RADAR="$APP/src/new-listing-radar.js"; RUN="$APP/run-paper.sh"; STATE=/var/lib/meme-alpha/data/micro-live/state.json; ARM=/etc/meme-alpha/micro-live-armed; SERVICE=meme-alpha-micro-live.service
STAMP=$(date -u +%Y%m%dT%H%M%SZ); B="$APP/runtime-status/v350-backup-$STAMP"; mkdir -p "$B"
cp -a "$DST" "$B/micro-live-executor.js"; cp -a "$RADAR" "$B/new-listing-radar.js"; cp -a "$RUN" "$B/run-paper.sh"; [ -f "$STATE" ] && cp -a "$STATE" "$B/state.json" || true; cp -a "$ARM" "$B/micro-live-armed"
for f in /etc/systemd/system/meme-alpha-realtime-pulse.service /etc/systemd/system/meme-alpha-whale-flow.service; do [ -f "$f" ] && cp -a "$f" "$B/$(basename "$f")" || true; done
BEFORE=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()))
NODE
)
rollback(){ rc=$?; if [ $rc -ne 0 ]; then echo V350_ROLLBACK_START=TRUE; printf 'ARMED=NO\n' > "$ARM" || true; systemctl stop "$SERVICE" meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service 2>/dev/null || true; cp -a "$B/micro-live-executor.js" "$DST" || true; cp -a "$B/new-listing-radar.js" "$RADAR" || true; cp -a "$B/run-paper.sh" "$RUN" || true; [ -f "$B/state.json" ] && cp -a "$B/state.json" "$STATE" || true; cp -a "$B/micro-live-armed" "$ARM" || true; for f in meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service; do [ -f "$B/$f" ] && cp -a "$B/$f" "/etc/systemd/system/$f" || rm -f "/etc/systemd/system/$f"; done; systemctl daemon-reload || true; systemctl restart meme-alpha-paper.service "$SERVICE" || true; echo V350_ROLLBACK_DONE=TRUE; fi; exit $rc; }
trap rollback EXIT
/usr/bin/node --check "$STAGE/micro-live-executor-v350-adaptive-alpha.js"; /usr/bin/node "$STAGE/micro-live-executor-v350-adaptive-alpha.js" --self-test | grep -q 'MICRO_EXECUTOR_V350_ADAPTIVE_ALPHA_SELF_TEST=PASS'
printf 'ARMED=NO\n' > "$ARM"; systemctl stop "$SERVICE"
install -o root -g root -m 0644 "$STAGE/micro-live-executor-v350-adaptive-alpha.js" "$DST"; install -o root -g root -m 0644 "$STAGE/new-listing-radar-v350.js" "$RADAR"; install -o root -g root -m 0644 "$STAGE/realtime-pool-pulse.js" "$APP/src/realtime-pool-pulse.js"; install -o root -g root -m 0644 "$STAGE/whale-flow-intel.js" "$APP/src/whale-flow-intel.js"
python3 - "$RUN" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text();s=re.sub(r'^LIVE_SIGNAL_MAX_AGE_SEC=\d+$','LIVE_SIGNAL_MAX_AGE_SEC=60',s,count=1,flags=re.M);s=s.replace('/usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1\n      sleep 5','/usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1\n      sleep 1',1);p.write_text(s)
PY
grep -q '^LIVE_SIGNAL_MAX_AGE_SEC=60$' "$RUN"; grep -q 'paperExecutionEnabled:false' "$RUN"; ! grep -q '/usr/bin/node src/position.js' "$RUN"
install -o meme-alpha -g meme-alpha -m 0664 /dev/null "$APP/runtime-status/realtime-pool-pulse.json"; install -o meme-alpha -g meme-alpha -m 0664 /dev/null "$APP/runtime-status/whale-flow-intel.json"
cat > /etc/systemd/system/meme-alpha-realtime-pulse.service <<'UNIT'
[Unit]
Description=Meme Alpha realtime pool pulse
After=network-online.target meme-alpha-paper.service
Wants=network-online.target
[Service]
Type=simple
User=meme-alpha
Group=meme-alpha
ExecStart=/usr/bin/node /opt/meme-alpha/app/src/realtime-pool-pulse.js
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/meme-alpha-whale-flow.service <<'UNIT'
[Unit]
Description=Meme Alpha on-chain whale flow intelligence
After=network-online.target meme-alpha-paper.service
Wants=network-online.target
[Service]
Type=simple
User=meme-alpha
Group=meme-alpha
ExecStart=/usr/bin/node /opt/meme-alpha/app/src/whale-flow-intel.js
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload; systemctl enable --now meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service; systemctl restart meme-alpha-paper.service; systemctl start "$SERVICE"; sleep 10
systemctl is-active --quiet "$SERVICE"; systemctl is-active --quiet meme-alpha-paper.service; systemctl is-active --quiet meme-alpha-realtime-pulse.service; systemctl is-active --quiet meme-alpha-whale-flow.service
[ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]
AFTER=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));if(s.version!=='3.50.0-adaptive-alpha')throw new Error('STATE_VERSION');console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()))
NODE
)
[ "$BEFORE" = "$AFTER" ] || { echo V350_POSITION_PRESERVATION_FAIL; exit 1; }
cp -a "$B/micro-live-armed" "$ARM"; systemctl restart "$SERVICE"; sleep 4; systemctl is-active --quiet "$SERVICE"
echo V350_BACKUP="$B"; echo PRESERVED_MINTS="$AFTER"; echo V350_ADAPTIVE_ALPHA_PRODUCTION_ACTIVE=TRUE
trap - EXIT
ROOT
chmod 0755 "$STAGE/install-v350.sh"
echo ROOT_INSTALL_COMMAND="$STAGE/install-v350.sh"
echo V350_STAGE_READY=TRUE
