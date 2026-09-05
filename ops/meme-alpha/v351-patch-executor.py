from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

def must(old,new,count=1):
    global s
    n=s.count(old)
    if n < count:
        raise SystemExit(f'PATCH_MISS {old[:120]!r} count={n}')
    s=s.replace(old,new,count)

def between(start,end,new):
    global s
    i=s.find(start)
    if i<0: raise SystemExit(f'START_MISS {start!r}')
    j=s.find(end,i)
    if j<0: raise SystemExit(f'END_MISS {end!r}')
    s=s[:i]+new+s[j:]

if '3.42.0-capital-utilization' not in s or 'CAPITAL_UTILIZATION_FIRST' not in s:
    raise SystemExit('V342_BASELINE_REQUIRED')

must("const TREND=`${APP}/runtime-status/trend-pulse.json`;","const TREND=`${APP}/runtime-status/trend-pulse.json`;\nconst REALTIME=`${APP}/runtime-status/realtime-pool-pulse.json`;\nconst WHALE=`${APP}/runtime-status/whale-flow-intel.json`;",1)
must("function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||null}","function signature(j){return j?.signature||j?.txid||j?.transactionSignature||j?.data?.signature||(typeof j?.result==='string'?j.result:null)||null}",1)

execute="""async function executeOrder(o){
  const cfg=read(`${APP}/config/runtime.json`),started=Date.now(),tx=o?.signedTransaction;
  if(typeof tx==='string'&&tx.length>200){
    const endpoints=['https://singapore.mainnet.block-engine.jito.wtf/api/v1/transactions','https://tokyo.mainnet.block-engine.jito.wtf/api/v1/transactions'];
    try{
      const landed=await Promise.any(endpoints.map(async url=>{const t=Date.now(),j=await post(url,{jsonrpc:'2.0',id:1,method:'sendTransaction',params:[tx,{encoding:'base64'}]});const sig=signature(j);if(!sig)throw new Error('JITO_NO_SIGNATURE');return{sig,url,submitMs:Date.now()-t}}));
      const confirmStart=Date.now();await confirm(landed.sig);event({type:'EXECUTION_FEEDBACK',route:'JITO_REGION_RACE',endpoint:landed.url,submitMs:landed.submitMs,confirmMs:Date.now()-confirmStart,totalMs:Date.now()-started,signature:landed.sig});return landed.sig;
    }catch(e){event({type:'EXECUTION_ROUTE_FALLBACK',from:'JITO_REGION_RACE',to:'JUPITER_EXECUTE',error:String(e?.message||e).slice(0,160)})}
  }
  const t=Date.now(),j=await post(`${String(cfg.jupiter).replace(/\\/$/,'')}/swap/v2/execute`,{signedTransaction:o.signedTransaction,requestId:o.requestId}),sig=signature(j);if(!sig)throw new Error('EXECUTE_NO_SIGNATURE');const submitMs=Date.now()-t,confirmStart=Date.now();await confirm(sig);event({type:'EXECUTION_FEEDBACK',route:'JUPITER_EXECUTE',submitMs,confirmMs:Date.now()-confirmStart,totalMs:Date.now()-started,signature:sig});return sig;
}

"""
between('async function executeOrder(o){','function candidates()',execute)
must("for(let i=0;i<30;i++){const r=await rpc('getSignatureStatuses'","for(let i=0;i<60;i++){const r=await rpc('getSignatureStatuses'",1)
must("await sleep(1000)}throw new Error('CHAIN_CONFIRM_TIMEOUT')","await sleep(400)}throw new Error('CHAIN_CONFIRM_TIMEOUT')",1)

helpers="""function intelRow(path,c,maxAgeSec=20){if(!c)return null;const x=read(path,{}),age=(Date.now()-Date.parse(x.updatedAt||0))/1000;if(!Number.isFinite(age)||age<0||age>maxAgeSec||x.status==='DEGRADED')return null;return (x.rows||[]).find(r=>r.mint===c.mint)||null}
function realtimeFor(c){return intelRow(REALTIME,c,8)}
function whaleFor(c){return intelRow(WHALE,c,45)}
function learningState(st){if(!st.learning||typeof st.learning!=='object')st.learning={version:1,totalClosed:0,totalWins:0,meanReturnPct:0,buckets:{}};if(!st.learning.buckets)st.learning.buckets={};return st.learning}
function featureKeys(c){const p=pulseFor(c),keys=[];keys.push(n(c.score)>=78?'SCORE_HIGH':n(c.score)>=68?'SCORE_MID':'SCORE_LOW');keys.push(n(c.liquidityUsd)>=500000?'LIQ_HIGH':n(c.liquidityUsd)>=150000?'LIQ_MID':'LIQ_LOW');keys.push(n(c.netBuyers5m)>=10?'FLOW_HIGH':n(c.netBuyers5m)>=3?'FLOW_MID':'FLOW_LOW');keys.push(n(p?.pulseScore)>=70?'PULSE_HIGH':n(p?.pulseScore)>=55?'PULSE_MID':'PULSE_LOW');keys.push(impact(c)<=.5?'IMPACT_LOW':impact(c)<=.9?'IMPACT_MID':'IMPACT_HIGH');const rt=realtimeFor(c);if(rt)keys.push(n(rt.eventMomentum)>=1.5&&n(rt.events5s)>=3?'RT_ACCEL':'RT_NORMAL');const w=whaleFor(c);if(w)keys.push(n(w.whaleFlowScore)>=2?'WHALE_HEALTHY':n(w.whaleFlowScore)<=-3?'WHALE_RISK':'WHALE_NEUTRAL');return keys}
function learnedBoost(st,c){const L=learningState(st),vals=[];for(const k of featureKeys(c)){const b=L.buckets[k];if(!b||n(b.count)<1)continue;const shrink=n(b.count)/(n(b.count)+18),m=clamp(n(b.meanReturnPct),-40,80);vals.push(m*shrink)}if(!vals.length)return 0;return clamp(vals.reduce((a,b)=>a+b,0)/vals.length/4,-8,12)}
function captureEntryFeatures(c,profile={}){return{keys:featureKeys(c),score:n(c.score),opportunityScore:opportunityScore(c),liquidityUsd:n(c.liquidityUsd),netBuyers5m:n(c.netBuyers5m),impactPct:impact(c),allocationPct:n(profile.pct),capturedAt:new Date().toISOString()}}
function learnClosedTrade(st,pos){const life=Math.max(1,n(pos.lifetimeCostLamports,n(pos.costBasisLamports))),pnl=n(pos.realizedPnlLamports),ret=clamp(pnl/life*100,-95,300),L=learningState(st);L.totalClosed=n(L.totalClosed)+1;L.totalWins=n(L.totalWins)+(ret>0?1:0);L.meanReturnPct+=(ret-n(L.meanReturnPct))/L.totalClosed;for(const k of pos.entryFeatures?.keys||[]){const b=L.buckets[k]||(L.buckets[k]={count:0,wins:0,meanReturnPct:0});b.count=n(b.count)+1;b.wins=n(b.wins)+(ret>0?1:0);b.meanReturnPct+=(ret-n(b.meanReturnPct))/b.count}event({type:'ONLINE_LEARNING_UPDATE',mint:pos.mint,symbol:pos.symbol,returnPct:ret,totalClosed:L.totalClosed,winRate:L.totalClosed?L.totalWins/L.totalClosed:0})}
function expectedEdge(st,c){return opportunityScore(c)+learnedBoost(st,c)}

"""
start='function opportunityScore(c){'
i=s.find(start)
if i<0: raise SystemExit('OPPORTUNITY_START_MISS')
s=s[:i]+helpers+s[i:]

opp="""function opportunityScore(c){const base=n(c.score),p=pulseFor(c);let add=0;if(p){if(n(p.volumeAcceleration)>=1.45)add+=4;else if(n(p.volumeAcceleration)>=1.10)add+=2;if(n(p.txnAcceleration)>=1.30)add+=3;else if(n(p.txnAcceleration)>=1.05)add+=1;if(n(p.buySellRatio)>=1.25)add+=2;if(themeStrength(c)>=60)add+=2;if(n(p.pulseScore)>=70)add+=1;if(p.status==='EXHAUSTED')add-=8;if(p.promotionFlag===true&&n(p.pulseScore)<65)add-=3}const rt=realtimeFor(c);if(rt&&n(rt.lastEventAgeMs,99999)<=2500){if(n(rt.eventMomentum)>=1.8&&n(rt.events5s)>=3)add+=5;else if(n(rt.events5s)>=2)add+=2}const w=whaleFor(c);if(w)add+=clamp(n(w.whaleFlowScore),-6,4);return clamp(base+add,base-10,base+18)}
"""
between('function opportunityScore(c){','function opportunityLane',opp)

allocation="""function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const rt=realtimeFor(c),rtQ=rt?clamp((n(rt.eventMomentum)-.8)/2.2,0,1):.35,w=whaleFor(c),whaleQ=w?clamp((n(w.whaleFlowScore)+10)/16,0,1):.50,learn=learnedBoost(st,c),learnQ=clamp(.5+learn/24,0,1);
  const quality=clamp(scoreQ*.26+netQ*.15+avgQ*.09+liqQ*.13+impactQ*.13+pulseQ*.08+rtQ*.07+whaleQ*.05+learnQ*.04,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.28),.80,2.00);
  const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1),basePct=4+31*Math.pow(quality,1.20),cashBoost=1+0.38*freeRatio,pct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct);
  return{name:'AUTO_ALPHA',pct,quality,growth,exposure,freeRatio,cashBoost,learnedBoost:learn,expectedEdge:expectedEdge(st,c),score:opportunityScore(c)};
}
"""
between('function allocationProfile(c,p,st,capitalBaseLamports){','function rank',allocation)

rankers="""function rank(c){const rt=realtimeFor(c),w=whaleFor(c);return opportunityScore(c)*100+n(c.netBuyers5m)*2+n(c.avgNetBuyersLast2)+n(c.organicRatio5m)*30+n(rt?.eventMomentum)*16+n(w?.whaleFlowScore)*8-Math.max(0,n(c.priceChange5m)-10)*10}
function bestCandidate(p,held,st){return candidates().filter(c=>!held.has(c.mint)&&trendEntryEligible(c)).sort((a,b)=>expectedEdge(st,b)-expectedEdge(st,a)||rank(b)-rank(a))[0]||null}

"""
between('function rank(c){','function normalizePosition',rankers)

must("pos.tp1Done=pos.tp1Done===true;pos.tp2Done=pos.tp2Done===true;pos.tp3Done=pos.tp3Done===true;pos.profitProtectDone=pos.profitProtectDone===true;pos.scaleInLockedAfterProfit=pos.scaleInLockedAfterProfit===true;\n  return pos;","pos.tp1Done=pos.tp1Done===true;pos.tp2Done=pos.tp2Done===true;pos.tp3Done=pos.tp3Done===true;pos.profitProtectDone=pos.profitProtectDone===true;pos.scaleInLockedAfterProfit=pos.scaleInLockedAfterProfit===true;\n  if(!Number.isFinite(Number(pos.lifetimeCostLamports)))pos.lifetimeCostLamports=n(pos.costBasisLamports);if(!Number.isFinite(Number(pos.realizedPnlLamports)))pos.realizedPnlLamports=0;\n  return pos;",1)
must("pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;","pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;pos.lifetimeCostLamports=n(pos.lifetimeCostLamports)+spent;",1)
must("st.positions.push(pos);event({type:'MICRO_BUY'","pos.entryFeatures=captureEntryFeatures(c,profile);pos.lifetimeCostLamports=spent;pos.realizedPnlLamports=0;st.positions.push(pos);event({type:'MICRO_BUY'",1)
must("const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){st.closed=n(st.closed)+1;st.positions.splice(index,1)}else{","pos.realizedPnlLamports=n(pos.realizedPnlLamports)+pnl;const fullyClosed=afterTok<=0n||f>=0.999;if(fullyClosed){learnClosedTrade(st,pos);st.closed=n(st.closed)+1;st.positions.splice(index,1)}else{",1)

rotation="""function rotationSource(st,newC){const ns=expectedEdge(st,newC),newImpact=impact(newC),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:expectedEdge(st,x.c),weak:softTrendWeak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);for(const x of rows){const switchingCost=(newImpact+Math.max(0,n(x.pos.lastPreviewImpactPct,impact(x.c))))*1.5,advantage=ns-x.oldScore-switchingCost;if(x.weak||advantage>=13){if(n(x.pos.lastReturnPct)>20&&!x.weak&&advantage<22)continue;return{...x,advantage,switchingCost}}}return null}
"""
between('function rotationSource(st,newC){','async function maybeRotate',rotation)
must('c=bestCandidate(p,held);','c=bestCandidate(p,held,st);',1)
must('now-last<10_000','now-last<5_000',1)
must("st.version='3.42.0-capital-utilization'","st.version='3.51.0-adaptive-alpha'",1)
must('MICRO_LIVE_EXECUTOR_V342_CAPITAL_UTILIZATION=STARTED','MICRO_LIVE_EXECUTOR_V351_ADAPTIVE_ALPHA=STARTED',1)
must('MICRO_EXECUTOR_V342_CAPITAL_UTILIZATION_SELF_TEST=PASS','MICRO_EXECUTOR_V351_ADAPTIVE_ALPHA_SELF_TEST=PASS',1)
must('await sleep(4000)','await sleep(1500)',1)
marker="console.log('NETWORK_EXECUTION=NOT_CALLED');"
must(marker,"console.log('REALTIME_POOL_PULSE_INTEGRATION=TRUE');console.log('ONCHAIN_WHALE_FLOW_INTEGRATION=TRUE');console.log('ONLINE_EXPECTANCY_LEARNING=TRUE');console.log('OPPORTUNITY_COST_ROTATION=TRUE');console.log('JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE');console.log('EXECUTION_FEEDBACK_LOOP=TRUE');console.log('ADAPTIVE_FAST_LOOP_MS=1500');"+marker,1)
p.write_text(s)
