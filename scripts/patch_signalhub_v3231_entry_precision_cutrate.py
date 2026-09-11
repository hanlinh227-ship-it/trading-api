from pathlib import Path
import re

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
api=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
monitor=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
gradle=Path('signalhub-android/app/build.gradle')

w=worker.read_text(); a=activity.read_text(); c=api.read_text(); m=monitor.read_text(); g=gradle.read_text()

def block(text,start,end,replacement,name):
    i=text.find(start); assert i>=0, f'{name}: start marker missing'
    j=text.find(end,i); assert j>i, f'{name}: end marker missing'
    return text[:i]+replacement+text[j:]

def once(text,old,new,name):
    assert old in text, f'{name}: marker missing'
    return text.replace(old,new,1)

# ---------------------------------------------------------------------------
# Identity. 3.23.1 is a focused quality release: stricter entry confirmation,
# less trigger-happy health cuts, and explicit cut-rate observability.
# ---------------------------------------------------------------------------
w=w.replace('SIGNALHUB-V3-GATEWAY-3.23.0','SIGNALHUB-V3-GATEWAY-3.23.1')
w=w.replace("SIGNALHUB_V3_CHECKPOINT_30_RESILIENT_LEDGER","SIGNALHUB_V3_CHECKPOINT_31_ENTRY_PRECISION_CUT_RATE")
w=w.replace("versionCode: 38,","versionCode: 39,")
w=w.replace("versionName: '3.23.0'","versionName: '3.23.1'")
w=w.replace("title: 'SignalHub 3.23.0 Resilient Ledger Clean'","title: 'SignalHub 3.23.1 Entry Precision Cut Rate'")
w=w.replace("artifactName: 'SignalHub-Android-v3.23.0-Resilient-Ledger-Clean'","artifactName: 'SignalHub-Android-v3.23.1-Entry-Precision-Cut-Rate'")
needle='  notes: [\n'; assert needle in w
w=w.replace(needle,needle+
"    'V3.23.1 tightens MARKET entry admission around multi-timeframe alignment, execution event/momentum agreement, anti-extension, liquidity and secondary-venue confirmation. The ranking is an internal quality ordering, not a predicted win probability.',\n"
"    'V3.23.1 reduces unnecessary AUTO_CUT churn with longer style-specific grace periods, warning hysteresis, structural-break confirmation and deeper adverse confirmation before retiring a signal.',\n"
"    'V3.23.1 exposes AUTO_CUT rate as AUTO_CUT/(TP+SL+AUTO_CUT), plus current-version cut rate, while strict TP/SL win rate remains unchanged and separate.',\n",1)

w=w.replace("primary-v3230-resilient-ledger-clean","primary-v3231-entry-precision-cutrate")
w=w.replace("V3230_REALTIME_SIGNAL_HEALTH_1S","V3231_PRECISION_HEALTH_HYSTERESIS_1S")
w=w.replace("V3230M-CRYPTO-","V3231M-CRYPTO-")
w=w.replace("qualityMode:'TOP_RANKED_MARKET_ONLY_WITH_HARD_SAFETY'","qualityMode:'PRECISION_MARKET_ENTRY_MULTI_CONFIRMATION_HARD_SAFETY'")
w=w.replace("entryModel:'STRUCTURE_LIQUIDITY_CONTEXT_MARKET_ONLY'","entryModel:'STRUCTURE_LIQUIDITY_CONTEXT_MULTI_CONFIRMATION_MARKET_ONLY'")

# ---------------------------------------------------------------------------
# Health policy: warnings still arrive early, but an AUTO_CUT now needs durable
# evidence. Normal pullbacks are allowed more room; real SL remains authoritative.
# ---------------------------------------------------------------------------
health=r'''const MARKET_HEALTH_POLICY=Object.freeze({
  watchR:-0.38,warningR:-0.62,persistentCutR:-0.86,structuralCutR:-0.74,emergencyCutR:-0.96,
  adverseTicksForCut:12,warningTicksForCut:14,structuralTicksForCut:9,stressedCutR:-0.82,
  profitProtectStartR:1.40,profitGivebackR:1.05,profitProtectFloorR:0.25,
  minAgeBeforeCutMs:{SCALP:90000,SWING:300000},emergencyMinAgeMs:30000,
  spreadStressMultiplier:2.80,liquidityStressRatio:0.50,recoveryTicksToClear:4,
  cutConfirmation:'STRUCTURE_BREAK_OR_DEEP_PERSISTENT_ADVERSE_OR_NEAR_SL_EMERGENCY',
  action:'SIGNAL_RETIRE_ONLY_USER_CLOSES_MANUAL_POSITION'
});

'''
w=block(w,'const MARKET_HEALTH_POLICY=Object.freeze({','const STYLE_EXECUTION_POLICY = Object.freeze({',health,'health policy')

# ---------------------------------------------------------------------------
# Precision MARKET admission. Compared with 3.23.0, extension, liquidity and
# confirmation gates are tighter. A no-secondary-data fallback is only allowed
# when all primary structure/momentum evidence agrees and liquidity is excellent.
# ---------------------------------------------------------------------------
converter=r'''function marketOnlySevenCandidate(raw){
  const s={...(raw||{})},style=String(s.style||'SCALP').toUpperCase(),side=String(s.side||'').toUpperCase(),dir=['LONG','BUY'].includes(side)?1:['SHORT','SELL'].includes(side)?-1:0,read=s.marketReadV322||{},tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{},src=Number(s.sourcePrice||s.lastPrice||s.entry||0),atr=Math.abs(Number(tech.atr||0));
  if(!dir||!(src>0&&atr>0))return null;
  const cross=s.crossProviderConsensus||{},checked=Number(cross.checked||0),confirmed=Number(cross.confirmed||0),opposed=Number(cross.opposed||0),crossStrong=opposed===0&&confirmed>=1,crossUnavailable=checked===0,crossQuality=crossStrong?'CONFIRMED':opposed>0?'OPPOSED':crossUnavailable?'UNAVAILABLE':'NEUTRAL';
  if(opposed>0)return null;
  const rule=stableUniverseRule(style),spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),move=Math.abs(Number(tech.change24hPct||0)),rsi=Number(tech.rsi||50),ext=Math.abs(Number(tech.extensionAtr||read.extensionAtr||0));
  const spreadCap=rule.maxSpread*(style==='SWING'?.90:.82),turnoverFloor=rule.minTurnover*(style==='SWING'?1.08:1.15);
  if(!(spread>=0&&spread<=spreadCap&&turnover>=turnoverFloor&&move<=rule.maxMove))return null;
  if((dir>0&&rsi>69)||(dir<0&&rsi<31))return null;
  const trends=Array.isArray(tech.tfTrend)?tech.tfTrend.map(x=>Number(x)>0?1:Number(x)<0?-1:0):[],derivedAligned=style==='SWING'?trends.length>=3&&trends[1]===dir&&trends[2]===dir:trends.length>=3&&trends[1]!==-dir&&trends[2]!==-dir&&(trends[1]===dir||trends[2]===dir),scalpStrong=style==='SCALP'&&trends.length>=3&&trends[1]===dir&&trends[2]===dir,contextAligned=read.contextAligned===true||ev.v322ContextAligned===true||derivedAligned,contextStrong=read.contextStrong===true||derivedAligned||scalpStrong,execEvent=read.executionEvent===true||Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),momentum=read.executionMomentum===true,evidenceCount=[contextStrong,execEvent,momentum].filter(Boolean).length;
  if(style==='SWING'&&!contextStrong)return null;if(style==='SCALP'&&!contextAligned)return null;
  const maxExt=style==='SWING'?.24:.30;if(ext>maxExt)return null;
  const excellentNoCross=crossUnavailable&&evidenceCount===3&&ext<=(style==='SWING'?.16:.20)&&spread<=spreadCap*.72&&turnover>=turnoverFloor*1.30;
  const strict=read.marketEntryReady===true&&contextStrong&&execEvent&&momentum&&crossStrong;
  const precisionAligned=contextAligned&&evidenceCount>=2&&(crossStrong||excellentNoCross);
  if(!strict&&!precisionAligned)return null;
  const spreadPx=Math.max(0,src*spread/10000),minRisk=atr*(style==='SWING'?1.05:.72),maxRisk=atr*(style==='SWING'?3.00:2.20),buffer=Math.max(atr*(style==='SWING'?.30:.22),spreadPx*3.5);
  const oldSl=Number(s.sl||0),inv=Number(s.invalidationLevel||0),recentLow=Number(tech.recentLow||0),recentHigh=Number(tech.recentHigh||0),ema50=Number(tech.ema50||0),anchors=dir>0?[inv,recentLow,oldSl,ema50].filter(x=>Number.isFinite(x)&&x>0&&x<src):[inv,recentHigh,oldSl,ema50].filter(x=>Number.isFinite(x)&&x>src);
  let anchor=anchors.length?(dir>0?Math.max(...anchors):Math.min(...anchors)):src-dir*minRisk,sl=anchor-dir*buffer,risk=Math.abs(src-sl);
  if(risk<minRisk){risk=minRisk;sl=src-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;
  const minRR=style==='SWING'?2.90:2.25,t1Base=src+dir*risk*1.00,t2Base=src+dir*risk*1.65,t3Base=src+dir*risk*minRR,oldT1=Number(s.tp1||0),oldT2=Number(s.tp2||0),oldT3=Number(s.tp3||s.tp||0);
  const useTarget=(old,base)=>dir>0?(old>src?Math.max(old,base):base):(old>0&&old<src?Math.min(old,base):base),tp1=useTarget(oldT1,t1Base),tp2=useTarget(oldT2,dir>0?Math.max(t2Base,tp1+risk*.25):Math.min(t2Base,tp1-risk*.25)),tp3=useTarget(oldT3,dir>0?Math.max(t3Base,tp2+risk*.35):Math.min(t3Base,tp2-risk*.35)),rr=Math.abs(tp3-src)/risk;
  if(rr<minRR)return null;
  return stampMarketJudgment({...s,orderType:'MARKET',status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',entry:Number(src.toPrecision(10)),actualEntry:Number(src.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),invalidationLevel:Number(anchor.toPrecision(10)),targetRR:Number(rr.toFixed(3)),coverageFallback:false,referenceFallback:false,marketOnly:true,marketOnlyQuality:strict?'PRECISION_CONFIRMED':'PRECISION_ALIGNED',marketOnlyFacts:{strict,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:momentum,evidenceCount,crossProvider:crossQuality,crossChecked:checked,crossConfirmed:confirmed,crossOpposed:opposed,extensionAtr:Number(ext.toFixed(3)),spreadBps:Number(spread.toFixed(3)),spreadCapBps:Number(spreadCap.toFixed(3)),turnover24h:turnover,targetRR:Number(rr.toFixed(3)),riskAtr:Number((risk/atr).toFixed(3))},entryAssessment:{verdict:'PASS',method:'V3231_PRECISION_MULTI_CONFIRMATION_ANTI_CHASE_NO_WIN_PROBABILITY',failed:[]}},'CRYPTO',style);
}
function compareMarketOnlyQuality(a,b){
  const aq=a.marketOnlyQuality==='PRECISION_CONFIRMED'?0:1,bq=b.marketOnlyQuality==='PRECISION_CONFIRMED'?0:1;if(aq!==bq)return aq-bq;const af=a.marketOnlyFacts||{},bf=b.marketOnlyFacts||{};
  if(Number(af.evidenceCount||0)!==Number(bf.evidenceCount||0))return Number(bf.evidenceCount||0)-Number(af.evidenceCount||0);
  const cr=x=>x==='CONFIRMED'?0:x==='NEUTRAL'?1:x==='UNAVAILABLE'?2:3,ac=cr(af.crossProvider),bc=cr(bf.crossProvider);if(ac!==bc)return ac-bc;
  if(Number(af.extensionAtr)!==Number(bf.extensionAtr))return Number(af.extensionAtr)-Number(bf.extensionAtr);
  if(Number(af.spreadBps)!==Number(bf.spreadBps))return Number(af.spreadBps)-Number(bf.spreadBps);
  if(Number(af.riskAtr)!==Number(bf.riskAtr))return Number(af.riskAtr)-Number(bf.riskAtr);
  if(Number(af.turnover24h)!==Number(bf.turnover24h))return Number(bf.turnover24h)-Number(af.turnover24h);
  return Number(bf.targetRR||0)-Number(af.targetRR||0);
}

'''
w=block(w,'function marketOnlySevenCandidate(raw){','async function maybeCreateV31(env,market,style,setups){',converter,'precision converter')

# ---------------------------------------------------------------------------
# Less trigger-happy health evaluator. TP/SL still use provider bid/ask. CUT is
# only allowed after confirmed deterioration; brief volatility produces WATCH/
# WARNING but is not retired immediately.
# ---------------------------------------------------------------------------
evaluate=r'''  async evaluate(market,rows,receivedAt){
    const reg=await this.registry(),by=new Map();
    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);const provider=String(q?.exchange||q?.provider||'').toUpperCase();if(provider)by.set(`${provider}:${sym}`,q);}
    const changed=[],at=receivedAt||nowIso();let dirty=false;
    for(const [id,s] of Object.entries(reg)){
      if(String(s.engineVersion||'')!==V3_VERSION)continue;
      if(String(s.market||'').toUpperCase()!==String(market||'').toUpperCase())continue;
      if(s.status!=='OPEN'||String(s.orderType||'MARKET').toUpperCase()!=='MARKET'){delete reg[id];dirty=true;continue;}
      const sym=canonical(s.symbol),authority=String(s.executionPriceAuthority||s.provider||s.exchange||'').toUpperCase(),q=authority?by.get(`${authority}:${sym}`):by.get(sym);if(!q)continue;
      const dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,last=Number(q.lastPrice||q.last||q.mid||0),bid=Number(q.bid||last||0),ask=Number(q.ask||last||0),exitPx=dir>0?bid:ask;if(!(exitPx>0))continue;
      const entry=Number(s.actualEntry||s.entry),sl=Number(s.sl),tp=Number(s.tp3||s.tp),risk=Math.abs(entry-sl);if(!(entry>0&&sl>0&&tp>0&&risk>0))continue;
      const hitTp=dir>0?exitPx>=tp:exitPx<=tp,hitSl=dir>0?exitPx<=sl:exitPx>=sl;
      if(hitTp||hitSl){
        const exit=hitTp?tp:sl;s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=exit;s.resultR=Number((dir*(exit-entry)/risk).toFixed(4));s.resolution='PROVIDER_BID_ASK_REALTIME_TRACKER';s.healthState=hitTp?'CLOSED_TP':'CLOSED_SL';s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean));await persistHistoryState(this.env,clean,clean.outcome,true);await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);const anyKey=`v31:active:any:${clean.market}:${clean.symbol}`,anyId=await this.env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===clean.id)await this.env.SIGNALS_KV.delete(anyKey);}
        delete reg[id];dirty=true;const evt={type:s.outcome,signal:clean,price:exitPx,at};changed.push(evt);this.broadcast({type:'signal_event',event:s.outcome,signal:clean,price:exitPx,receivedAt:at});continue;
      }
      const r=dir*(exitPx-entry)/risk,prev=Number(s.healthLastPrice||entry),adverseStep=dir>0?exitPx<prev:exitPx>prev;
      let adverseTicks=Number(s.healthAdverseTicks||0);adverseTicks=adverseStep&&r<-.24?Math.min(90,adverseTicks+1):Math.max(0,adverseTicks-1);
      const bestR=Math.max(Number.isFinite(Number(s.healthBestR))?Number(s.healthBestR):r,r),worstR=Math.min(Number.isFinite(Number(s.healthWorstR))?Number(s.healthWorstR):r,r),style=String(s.style||'SCALP').toUpperCase(),rule=stableUniverseRule(style),tech=s.technicalAtIssue||{},spread=Number(q.spreadBps??tech.spreadBps??0),baseSpread=Math.max(.01,Number(tech.spreadBps??spread??.01)),turnover=Number(q.turnover24h||q.turnover24hQuote||tech.turnover24h||0),spreadStress=spread>Math.max(rule.maxSpread*1.65,baseSpread*MARKET_HEALTH_POLICY.spreadStressMultiplier),liquidityStress=turnover>0&&turnover<rule.minTurnover*MARKET_HEALTH_POLICY.liquidityStressRatio,giveback=bestR>=MARKET_HEALTH_POLICY.profitProtectStartR&&r<=bestR-MARKET_HEALTH_POLICY.profitGivebackR;
      const invalidation=Number(s.invalidationLevel||0),structureBroken=invalidation>0&&(dir>0?exitPx<=invalidation:exitPx>=invalidation);
      let health='HEALTHY',reason='STRUCTURE_HOLDING';
      if(giveback&&r>=MARKET_HEALTH_POLICY.profitProtectFloorR){health='WARNING';reason='PROFIT_GIVEBACK';}
      else if(structureBroken&&r<=MARKET_HEALTH_POLICY.warningR){health='WARNING';reason='STRUCTURE_BREAK_PRESSURE';}
      else if(r<=MARKET_HEALTH_POLICY.warningR&&adverseTicks>=5){health='WARNING';reason='PERSISTENT_ADVERSE_MOVE';}
      else if((spreadStress||liquidityStress)&&r<=-.45){health='WARNING';reason=spreadStress?'SPREAD_STRESS':'LIQUIDITY_STRESS';}
      else if(r<=MARKET_HEALTH_POLICY.watchR||spreadStress||liquidityStress){health='WATCH';reason=spreadStress?'SPREAD_WIDENING':liquidityStress?'LIQUIDITY_WEAKENING':'ADVERSE_EXCURSION';}
      let warningTicks=Number(s.healthWarningTicks||0);warningTicks=health==='WARNING'?Math.min(120,warningTicks+1):Math.max(0,warningTicks-2);
      let recoveryTicks=Number(s.healthRecoveryTicks||0);recoveryTicks=health==='HEALTHY'?Math.min(30,recoveryTicks+1):0;
      const issued=Date.parse(s.issuedAt||s.triggeredAt||''),ageMs=Number.isFinite(issued)?Math.max(0,Date.now()-issued):0,minAge=style==='SWING'?MARKET_HEALTH_POLICY.minAgeBeforeCutMs.SWING:MARKET_HEALTH_POLICY.minAgeBeforeCutMs.SCALP;
      const emergency=ageMs>=MARKET_HEALTH_POLICY.emergencyMinAgeMs&&r<=MARKET_HEALTH_POLICY.emergencyCutR;
      const structural=ageMs>=minAge&&structureBroken&&r<=MARKET_HEALTH_POLICY.structuralCutR&&adverseTicks>=MARKET_HEALTH_POLICY.structuralTicksForCut&&warningTicks>=10;
      const persistent=ageMs>=minAge&&r<=MARKET_HEALTH_POLICY.persistentCutR&&adverseTicks>=MARKET_HEALTH_POLICY.adverseTicksForCut&&warningTicks>=MARKET_HEALTH_POLICY.warningTicksForCut;
      const stressed=ageMs>=minAge&&r<=MARKET_HEALTH_POLICY.stressedCutR&&warningTicks>=16&&adverseTicks>=10&&(spreadStress||liquidityStress);
      const protect=ageMs>=minAge&&bestR>=MARKET_HEALTH_POLICY.profitProtectStartR&&r>=MARKET_HEALTH_POLICY.profitProtectFloorR&&giveback&&adverseTicks>=7&&warningTicks>=6;
      if(emergency||structural||persistent||stressed||protect){
        s.status='CLOSED';s.outcome='AUTO_CUT';s.lifecycle=protect?'AUTO_CUT_PROFIT_PROTECT':'AUTO_CUT_CONFIRMED_DETERIORATION';s.closedAt=at;s.exitPrice=exitPx;s.resultR=Number(r.toFixed(4));s.resolution='V3231_CONFIRMED_HEALTH_GUARD_SIGNAL_ONLY';s.healthState='CUT';s.healthReason=protect?'PROFIT_GIVEBACK':emergency?'NEAR_SL_EMERGENCY':structural?'CONFIRMED_STRUCTURE_BREAK':stressed?'LIQUIDITY_OR_SPREAD_STRESS_CONFIRMED':'DEEP_PERSISTENT_ADVERSE';s.manualAction='CLOSE_MANUALLY_AND_WAIT_REPLACEMENT';s.executionAction='SIGNAL_RETIRED_ONLY_NO_BROKER_EXECUTION';s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean));await persistHistoryState(this.env,clean,'AUTO_CUT',true);await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);const anyKey=`v31:active:any:${clean.market}:${clean.symbol}`,anyId=await this.env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===clean.id)await this.env.SIGNALS_KV.delete(anyKey);}
        delete reg[id];dirty=true;const evt={type:'AUTO_CUT',signal:clean,price:exitPx,at};changed.push(evt);this.broadcast({type:'signal_event',event:'AUTO_CUT',signal:clean,price:exitPx,receivedAt:at});continue;
      }
      const oldHealth=String(s.healthState||'HEALTHY');if(oldHealth==='WARNING'&&health==='HEALTHY'&&recoveryTicks<MARKET_HEALTH_POLICY.recoveryTicksToClear){health='WATCH';reason='RECOVERY_CONFIRMATION';}
      s.healthState=health;s.healthReason=reason;s.healthR=Number(r.toFixed(4));s.healthBestR=Number(bestR.toFixed(4));s.healthWorstR=Number(worstR.toFixed(4));s.healthAdverseTicks=adverseTicks;s.healthWarningTicks=warningTicks;s.healthRecoveryTicks=recoveryTicks;s.healthLastPrice=exitPx;s.lastPrice=exitPx;s.lastCheckedAt=at;s.healthUpdatedAt=at;s.manualTradeMonitoring=true;s.executionAction='SIGNAL_ONLY_USER_MANUAL_EXECUTION';dirty=true;
      if(oldHealth!==health){const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean));await persistHistoryState(this.env,clean,health,false);}const event=health==='WARNING'?'HEALTH_WARNING':health==='WATCH'?'HEALTH_WATCH':'HEALTH_RECOVERED';changed.push({type:event,signal:clean,price:exitPx,at});this.broadcast({type:'signal_event',event,signal:clean,price:exitPx,receivedAt:at});}
    }
    if(dirty)await this.persistRegistry();return changed;
  }
'''
w=block(w,'  async evaluate(market,rows,receivedAt){','  async fetch(req) {',evaluate,'health evaluator')

# ---------------------------------------------------------------------------
# Performance: preserve strict TP/SL WR and add cut-rate observability. The
# current-version metric lets the user see whether the new policy actually
# reduces cut churn instead of mixing it invisibly with old history.
# ---------------------------------------------------------------------------
perf=r'''async function unifiedPerformance(url,env){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_PRECISION',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=await getV31HistorySignals(env,market,style),active=rows.filter(s=>String(s.engineVersion||'')===V3_VERSION&&s.status==='OPEN'),tpSl=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),cuts=rows.filter(s=>s.status==='CLOSED'&&s.outcome==='AUTO_CUT'),allResolved=[...tpSl,...cuts],tp=tpSl.filter(s=>s.outcome==='TP').length,sl=tpSl.filter(s=>s.outcome==='SL').length,cutProfit=cuts.filter(s=>Number(s.resultR||0)>0).length,cutLoss=cuts.length-cutProfit,netR=allResolved.reduce((z,s)=>z+Number(s.resultR||0),0),wr=tpSl.length?tp/tpSl.length*100:null,allWins=allResolved.filter(s=>Number(s.resultR||0)>0).length,allWr=allResolved.length?allWins/allResolved.length*100:null,cutRate=allResolved.length?cuts.length/allResolved.length*100:null,cutLossRate=allResolved.length?cutLoss/allResolved.length*100:null;
  const currentClosed=rows.filter(s=>String(s.engineVersion||'')===V3_VERSION&&s.status==='CLOSED'&&['TP','SL','AUTO_CUT'].includes(String(s.outcome||''))),currentCuts=currentClosed.filter(s=>s.outcome==='AUTO_CUT'),currentCutRate=currentClosed.length?currentCuts.length/currentClosed.length*100:null;
  const fmt=(v,n,d)=>n?`${v.toFixed(1)}% (${d}/${n})`:'CHƯA CÓ MẪU';
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_PRECISION',market,style,performance:{retentionDays:null,total:rows.length,active:active.length,pending:0,open:active.length,resolved:tpSl.length,tp,sl,winRateResolved:wr,winRateLabel:tpSl.length?`${wr.toFixed(1)}% (${tp}/${tpSl.length})`:'CHƯA CÓ MẪU TP/SL',autoCut:cuts.length,autoCutProfit:cutProfit,autoCutLoss:cutLoss,autoCutRate:cutRate,autoCutRateLabel:fmt(cutRate||0,allResolved.length,cuts.length),autoCutLossRate:cutLossRate,autoCutRateDefinition:'AUTO_CUT/(TP+SL+AUTO_CUT)',currentVersion:V3_VERSION,currentVersionClosed:currentClosed.length,currentVersionAutoCut:currentCuts.length,currentVersionAutoCutRate:currentCutRate,currentVersionAutoCutRateLabel:fmt(currentCutRate||0,currentClosed.length,currentCuts.length),allResolved:allResolved.length,allWins,winRateAllResolved:allWr,winRateAllLabel:allResolved.length?`${allWr.toFixed(1)}% (${allWins}/${allResolved.length})`:'CHƯA CÓ MẪU',netRResolved:Number(netR.toFixed(2)),sampleAdequate:allResolved.length>=50,policy:'HISTORY_PERMANENT_NO_TTL; TP_SL_WR_STRICT; AUTO_CUT_SEPARATE; CUT_RATE=AUTO_CUT/(TP+SL+AUTO_CUT); CURRENT_VERSION_CUT_RATE_SEPARATE'}});
}

'''
w=block(w,'async function unifiedPerformance(url,env){','async function scanRoute',perf,'performance cut rate')

stability=r'''async function v315Stability(env){
  const portfolio=await realtimePortfolioSnapshot(env),monitor=await cryptoServerMonitorStatus(env),styles={};let totalResolved=0,totalTp=0,totalSl=0,totalCuts=0,totalAll=0,totalWins=0,totalNetR=0,currentClosed=0,currentCuts=0;
  for(const style of ['SCALP','SWING']){const rows=await getV31HistorySignals(env,'CRYPTO',style),tpSl=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),cuts=rows.filter(s=>s.status==='CLOSED'&&s.outcome==='AUTO_CUT'),tp=tpSl.filter(s=>s.outcome==='TP').length,sl=tpSl.filter(s=>s.outcome==='SL').length,all=[...tpSl,...cuts],wins=all.filter(s=>Number(s.resultR||0)>0).length,netR=all.reduce((z,s)=>z+Number(s.resultR||0),0),wr=tpSl.length?tp/tpSl.length*100:null,allWr=all.length?wins/all.length*100:null,cutRate=all.length?cuts.length/all.length*100:null,cur=rows.filter(s=>String(s.engineVersion||'')===V3_VERSION&&s.status==='CLOSED'&&['TP','SL','AUTO_CUT'].includes(String(s.outcome||''))),curCuts=cur.filter(s=>s.outcome==='AUTO_CUT'),curRate=cur.length?curCuts.length/cur.length*100:null;styles[style]={resolved:tpSl.length,tp,sl,winRateResolved:wr,autoCut:cuts.length,autoCutRate:cutRate,currentVersionClosed:cur.length,currentVersionAutoCut:curCuts.length,currentVersionAutoCutRate:curRate,allResolved:all.length,winRateAllResolved:allWr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:all.length>=50,evidenceState:all.length>=50?'MATURE_SAMPLE':all.length>=15?'BUILDING_SAMPLE':'INSUFFICIENT_SAMPLE'};totalResolved+=tpSl.length;totalTp+=tp;totalSl+=sl;totalCuts+=cuts.length;totalAll+=all.length;totalWins+=wins;totalNetR+=netR;currentClosed+=cur.length;currentCuts+=curCuts.length;}
  const monitorHealthy=monitor?.ok!==false&&monitor?.running!==false&&Array.isArray(monitor?.errors)&&monitor.errors.length===0,warnings=[];if(totalAll<50)warnings.push('PERFORMANCE_SAMPLE_SMALL');if(!monitorHealthy)warnings.push('CRYPTO_MONITOR_DEGRADED');if(!portfolio.exactTarget)warnings.push('ACTIVE_BOOK_NOT_EXACT_5_2');
  return json({ok:true,version:V3_VERSION,checkpoint:CHECKPOINT,mode:'CRYPTO_MARKET_ONLY_PRECISION',infrastructure:{state:monitorHealthy?'STABLE':'DEGRADED',monitor,portfolio},tradingEvidence:{state:totalAll>=100?'MATURE':'NOT_YET_PROVEN',retentionDays:null,resolvedTpSl:totalResolved,tp:totalTp,sl:totalSl,strictWinRateResolved:totalResolved?totalTp/totalResolved*100:null,autoCut:totalCuts,autoCutRate:totalAll?totalCuts/totalAll*100:null,autoCutRateDefinition:'AUTO_CUT/(TP+SL+AUTO_CUT)',currentVersion:V3_VERSION,currentVersionClosed:currentClosed,currentVersionAutoCut:currentCuts,currentVersionAutoCutRate:currentClosed?currentCuts/currentClosed*100:null,allResolved:totalAll,allExitWinRate:totalAll?totalWins/totalAll*100:null,netRResolved:Number(totalNetR.toFixed(2)),styles},warnings,note:'Strict TP/SL WR is separate from AUTO_CUT. Cut rate measures AUTO_CUT share of all terminal exits; current-version cut rate is exposed separately to evaluate the new precision/health policy.'});
}

'''
w=block(w,'async function v315Stability(env){','async function v3Status',stability,'stability cut rate')

# Android performance line: make cut rate visible at a glance, including the new
# version-only rate so improvements are not hidden by older aggressive cuts.
perf_ui='    private String performanceSummary(){JSONObject p=perfCache.get("CRYPTO:"+style);if(p==null)return "Chưa đủ dữ liệu đóng lệnh";int cuts=p.optInt("autoCut",0),all=p.optInt("allResolved",0),curN=p.optInt("currentVersionClosed",0);String wr=p.optString("winRateLabel","—"),allWr=p.optString("winRateAllLabel","—"),cut=p.optString("autoCutRateLabel","—"),cur=curN>0?p.optString("currentVersionAutoCutRateLabel","—"):"chưa có mẫu";return "WR TP/SL "+wr+" • TỈ LỆ CUT "+cut+" • V3.23.1 "+cur+" • EXIT WR "+allWr+" • "+cuts+" CUT / "+all+" mẫu • Net "+String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0));}\n'
a=block(a,'    private String performanceSummary(){','    private View signalCard(JSONObject s){',perf_ui,'Android performanceSummary')

# Version labels / transport identity.
a=a.replace('APP_VERSION="3.23.0"','APP_VERSION="3.23.1"')
a=a.replace('SignalHub V3.23.0','SignalHub V3.23.1').replace('SignalHub 3.23.0','SignalHub 3.23.1')
c=c.replace('SignalHub-Android/3.23.0','SignalHub-Android/3.23.1')
m=m.replace('SignalHub V3.23.0','SignalHub V3.23.1').replace('SignalHub 3.23.0','SignalHub 3.23.1')
g=g.replace('versionCode 38','versionCode 39').replace("versionName '3.23.0'","versionName '3.23.1'")

# Make status/debug strings identify the precision release without touching API paths.
w=w.replace("mode:'CRYPTO_MARKET_ONLY_RESILIENT_LEDGER'","mode:'CRYPTO_MARKET_ONLY_PRECISION'")
w=w.replace('V3.23.0 final admission is MARKET-only 5 SCALP + 2 SWING.','V3.23.1 precision admission is MARKET-only 5 SCALP + 2 SWING.')

worker.write_text(w); activity.write_text(a); api.write_text(c); monitor.write_text(m); gradle.write_text(g)

# Hard invariants for this release.
assert 'SIGNALHUB-V3-GATEWAY-3.23.1' in w
assert 'SIGNALHUB_V3_CHECKPOINT_31_ENTRY_PRECISION_CUT_RATE' in w
assert 'primary-v3231-entry-precision-cutrate' in w
assert "watchR:-0.38" in w and "persistentCutR:-0.86" in w and "emergencyCutR:-0.96" in w
assert 'V3231_PRECISION_MULTI_CONFIRMATION_ANTI_CHASE_NO_WIN_PROBABILITY' in w
assert "marketOnlyQuality:strict?'PRECISION_CONFIRMED':'PRECISION_ALIGNED'" in w
assert 'autoCutRateDefinition' in w and 'currentVersionAutoCutRate' in w
assert 'TỈ LỆ CUT' in a and 'V3.23.1' in a
assert 'APP_VERSION="3.23.1"' in a and 'SignalHub-Android/3.23.1' in c
assert 'versionCode 39' in g and "versionName '3.23.1'" in g
assert w.count('const PORTFOLIO_POLICY=Object.freeze(')==1
assert "targetActiveByStyle:{SCALP:5,SWING:2}" in w
print('patched SignalHub V3.23.1 precision entry + reduced cut churn + cut-rate tracking')
