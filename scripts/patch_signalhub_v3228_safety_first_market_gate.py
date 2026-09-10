from pathlib import Path

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

# Identity
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.7','SIGNALHUB-V3-GATEWAY-3.22.8')
w=w.replace("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_20';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_21';")
w=w.replace("versionCode: 36,","versionCode: 37,")
w=w.replace("versionName: '3.22.7'","versionName: '3.22.8'")
w=w.replace("title: 'SignalHub 3.22.7 Market-Only Health Seven'","title: 'SignalHub 3.22.8 Safety-First Market Gate'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.7-Market-Only-Health-Seven'","artifactName: 'SignalHub-Android-v3.22.8-Safety-First-Market-Gate'")
needle='  notes: [\n'
assert needle in w
w=w.replace(needle,needle+"    'V3.22.8 makes quality and data integrity higher priority than filling all seven slots: 5 SCALP and 2 SWING are hard maximum targets, never forced quotas.',\n    'V3.22.8 removes the remaining V3.22.6 15-slot runtime policy so status, scanner, Durable Object reservation, portfolio and app-facing reads all use one 7-slot policy.',\n    'V3.22.8 adds a final publication gate: stale/legacy/non-MARKET/malformed/duplicate or hard-conflict rows are not allowed onto the active app feed.',\n    'V3.22.8 keeps strict TP/SL historical win rate separate from AUTO_CUT and keeps AUTO_CUT as a signal retirement warning unless broker execution is explicitly connected.',\n",1)

# One canonical policy. Targets are caps, not forced quotas.
policy=r'''const MARKET_JUDGMENT_POLICY = Object.freeze({
  name:'CRYPTO_SAFETY_FIRST_MARKET_JUDGMENT',
  scoreGate:false,
  timeGate:false,
  rrGate:false,
  orderRouting:'MARKET_ONLY_UP_TO_5_SCALP_2_SWING',
  historicalWinRateMode:'RESOLVED_TP_SL_PRIMARY_AUTO_CUT_SEPARATE',
  performanceRetentionDays:365,
  entryModel:'CURRENT_PRICE_STRUCTURE_LIQUIDITY_CONTEXT_MARKET_ONLY',
  stopModel:'INVALIDATION_STRUCTURE_PLUS_VOLATILITY_BUFFER',
  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION',
  styleSeparation:'SCALP_MICROSTRUCTURE_VS_SWING_HTF_STRUCTURE',
  pendingActivation:'DISABLED_MARKET_ONLY',
  qualityMode:'QUALITY_FIRST_NO_FORCED_FILL_WITH_FINAL_PUBLICATION_GATE',
  lifecycleSource:'DURABLE_OBJECT_REALTIME_SINGLE_SOURCE',
  healthModel:'V3228_REALTIME_SIGNAL_HEALTH_1S',
  autoCutExecution:'SIGNAL_RETIRE_ONLY_NO_BROKER_EXECUTION',
  portfolioPolicy:{maxActiveTotal:7,maxActivePerMarket:7,maxActivePerStyle:5,maxNewPerScan:5,minActivePerMarket:0,minActivePerStyle:0,targetActivePerStyle:5,targetActiveByStyle:{SCALP:5,SWING:2},maxActiveByStyle:{SCALP:5,SWING:2},maxNewPerScanByStyle:{SCALP:5,SWING:2},maxActivePerRiskCluster:7,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_UP_TO_5_SCALP_2_SWING_MARKET_ONLY_QUALITY_FIRST',cryptoPendingMonitor:'DISABLED_MARKET_ONLY',cryptoHealthMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:0,replacementMode:'HEALTH_CUT_THEN_ASYNC_QUALITY_RESCAN',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'SEARCH_TO_TARGET_WITHOUT_FORCING_WEAK_MARKET_ENTRY',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT',forexDisabled:true}
});

'''
w=block(w,'const MARKET_JUDGMENT_POLICY = Object.freeze({','const MARKET_HEALTH_POLICY=Object.freeze({',policy,'decision policy')

health=r'''const MARKET_HEALTH_POLICY=Object.freeze({
  watchR:-0.30,warningR:-0.50,persistentCutR:-0.72,emergencyCutR:-0.92,
  adverseTicksForCut:8,warningTicksForCut:10,stressedCutR:-0.65,
  profitProtectStartR:1.20,profitGivebackR:0.78,
  minAgeBeforeCutMs:{SCALP:90000,SWING:300000},
  spreadStressMultiplier:2.30,liquidityStressRatio:0.58,
  action:'SIGNAL_RETIRE_ONLY_USER_CLOSES_MANUAL_POSITION'
});

'''
w=block(w,'const MARKET_HEALTH_POLICY=Object.freeze({','const STYLE_EXECUTION_POLICY = Object.freeze({',health,'health policy')

portfolio=r'''const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:7,maxActivePerMarket:7,maxActivePerStyle:5,maxNewPerScan:5,minActivePerMarket:0,minActivePerStyle:0,targetActivePerStyle:5,targetActiveByStyle:{SCALP:5,SWING:2},maxActiveByStyle:{SCALP:5,SWING:2},maxNewPerScanByStyle:{SCALP:5,SWING:2},maxActivePerRiskCluster:7,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_UP_TO_5_SCALP_2_SWING_MARKET_ONLY_QUALITY_FIRST',cryptoPendingMonitor:'DISABLED_MARKET_ONLY',cryptoHealthMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:0,replacementMode:'HEALTH_CUT_THEN_ASYNC_QUALITY_RESCAN',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'SEARCH_TO_TARGET_WITHOUT_FORCING_WEAK_MARKET_ENTRY',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT',forexDisabled:true});
'''
w=block(w,'const PORTFOLIO_POLICY=Object.freeze({','function styleTarget(style){',portfolio,'canonical portfolio policy')

# Market-only quality conversion. This can convert an analytically valid pending-shaped
# plan to CURRENT MARKET only when current price is still inside a valid target path.
market_helpers=r'''function marketOnlySevenCandidate(raw){
  const s={...(raw||{})},style=String(s.style||'SCALP').toUpperCase(),side=String(s.side||'').toUpperCase(),dir=['LONG','BUY'].includes(side)?1:['SHORT','SELL'].includes(side)?-1:0;
  const read=s.marketReadV322||{},tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{},crossObj=s.crossProviderConsensus||{},cross=String(crossObj.state||'UNAVAILABLE').toUpperCase(),src=Number(s.sourcePrice||s.lastPrice||0),oldEntry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp);
  if(!dir||!(src>0&&oldEntry>0&&sl>0&&t1>0&&t2>0&&t3>0))return null;
  if(read.hardConflict===true||cross==='OPPOSED')return null;
  if(dir>0&&!(sl<src&&src<t1&&t1<t2&&t2<t3))return null;
  if(dir<0&&!(sl>src&&src>t1&&t1>t2&&t2>t3))return null;
  if(ev.invalidationStructural===false||ev.targetPathClear===false)return null;
  const oldRisk=Math.abs(oldEntry-sl),risk=Math.abs(src-sl);if(!(oldRisk>0&&risk>0))return null;
  const driftR=Math.abs(src-oldEntry)/oldRisk,rr=Math.abs(t3-src)/risk,spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),move=Math.abs(Number(tech.change24hPct||0)),ext=Math.abs(Number(tech.extensionAtr??read.extensionAtr??999)),rsi=Number(tech.rsi||50),oi=tech.openInterestValue==null?null:Number(tech.openInterestValue),fund=tech.fundingRate==null?null:Math.abs(Number(tech.fundingRate)),rule=stableUniverseRule(style);
  const contextAligned=read.contextAligned===true,contextStrong=read.contextStrong===true,execEvent=read.executionEvent===true||Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed)||Boolean(ev.structureReclaimed),momentum=read.executionMomentum===true;
  if(!contextAligned||!momentum)return null;
  if(style==='SWING'&&!contextStrong)return null;
  if(style==='SCALP'&&!(execEvent||contextStrong))return null;
  if(!(spread>=0&&spread<=rule.maxSpread&&turnover>=rule.minTurnover&&move<=rule.maxMove))return null;
  if(oi!=null&&Number.isFinite(oi)&&oi>0&&oi<rule.minOi)return null;
  if(fund!=null&&Number.isFinite(fund)&&fund>rule.maxFunding)return null;
  const maxExt=style==='SWING'?.28:.34,maxDrift=style==='SWING'?.45:.55;if(ext>maxExt||driftR>maxDrift)return null;
  if((dir>0&&rsi>70)||(dir<0&&rsi<30))return null;
  const minRR=style==='SWING'?2.60:2.05;if(rr<minRR)return null;
  const checked=Number(crossObj.checked||0),strict=read.marketEntryReady===true&&contextStrong&&execEvent&&momentum&&cross==='CONFIRMED';
  const crossSafe=cross==='CONFIRMED'||cross==='UNAVAILABLE'||(cross==='NEUTRAL'&&checked>=1&&contextStrong&&execEvent);if(!crossSafe)return null;
  const tier=strict?'STRICT_CONFIRMED':'CONFIRMED_SAFE';
  return {...s,orderType:'MARKET',entry:src,actualEntry:src,status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',targetRR:Number(rr.toFixed(3)),coverageFallback:false,marketOnly:true,marketOnlyQuality:tier,marketOnlyFacts:{strict,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:momentum,crossProvider:cross,crossChecked:checked,extensionAtr:Number(ext.toFixed(3)),driftR:Number(driftR.toFixed(3)),spreadBps:spread,turnover24h:turnover,targetRR:Number(rr.toFixed(3))},entryAssessment:{verdict:'PASS',method:'V3228_SAFETY_FIRST_CURRENT_MARKET_STRUCTURE_CONTEXT_LIQUIDITY',failed:[]}};
}
function compareMarketOnlyQuality(a,b){
  const ax=a.marketOnlyQuality==='STRICT_CONFIRMED'?0:1,bx=b.marketOnlyQuality==='STRICT_CONFIRMED'?0:1;if(ax!==bx)return ax-bx;const af=a.marketOnlyFacts||{},bf=b.marketOnlyFacts||{};
  for(const k of ['contextStrong','executionEvent','executionMomentum']){const av=af[k]?0:1,bv=bf[k]?0:1;if(av!==bv)return av-bv;}
  if(String(af.crossProvider)!==String(bf.crossProvider)){if(af.crossProvider==='CONFIRMED')return-1;if(bf.crossProvider==='CONFIRMED')return 1;}
  if(Number(af.spreadBps)!==Number(bf.spreadBps))return Number(af.spreadBps)-Number(bf.spreadBps);
  if(Number(af.extensionAtr)!==Number(bf.extensionAtr))return Number(af.extensionAtr)-Number(bf.extensionAtr);
  if(Number(af.driftR)!==Number(bf.driftR))return Number(af.driftR)-Number(bf.driftR);
  if(Number(af.turnover24h)!==Number(bf.turnover24h))return Number(bf.turnover24h)-Number(af.turnover24h);
  return Number(bf.targetRR||0)-Number(af.targetRR||0);
}

'''
w=block(w,'function marketOnlySevenCandidate(raw){','function setupPriority(s){',market_helpers,'market candidate gate')

# Quality-first maintenance: search toward target, never force a weak setup.
maintenance=r'''async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SWING','SCALP']){
    const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'QUALITY_RESCAN':'AT_TARGET'}`);
    if(underfilled){await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  await kickCryptoServerMonitor(env).catch(()=>{});
  return {mode:'QUALITY_FIRST_UP_TO_5_SCALP_2_SWING_MARKET_ONLY',attempted,portfolio:p,healthPolicy:MARKET_HEALTH_POLICY,standbys:{disabled:true},forcedFill:false};
}

'''
w=block(w,'async function cryptoOnlyMaintenance(env){','async function exnessQuoteMap',maintenance,'maintenance')

# App-facing publication gate is independent of scanner creation. Invalid or legacy rows
# cannot leak onto the active feed even if stale state remains in KV/DO.
signals=r'''function publicationGateV3228(s,style){
  if(!s||String(s.engineVersion||'')!==V3_VERSION)return false;
  if(String(s.market||'').toUpperCase()!=='CRYPTO'||String(s.style||'').toUpperCase()!==style)return false;
  if(String(s.status||'').toUpperCase()!=='OPEN'||String(s.orderType||'MARKET').toUpperCase()!=='MARKET')return false;
  if(!validSignalStructure(s))return false;
  const p=String(s.executionPriceAuthority||s.provider||s.exchange||'').toUpperCase();if(!['BYBIT','OKX','BINANCE'].includes(p))return false;
  const e=Number(s.entry||0),sl=Number(s.sl||0),tp=Number(s.tp3||s.tp||0);if(!(e>0&&sl>0&&tp>0))return false;
  const side=String(s.side||'').toUpperCase(),dir=['LONG','BUY'].includes(side)?1:['SHORT','SELL'].includes(side)?-1:0;if(!dir)return false;
  if(dir>0&&!(sl<e&&tp>e))return false;if(dir<0&&!(sl>e&&tp<e))return false;
  if(String(s.entryAssessment?.verdict||'PASS').toUpperCase()!=='PASS')return false;
  if(String(s.healthState||'HEALTHY').toUpperCase()==='CUT')return false;
  if(s.marketReadV322?.hardConflict===true||String(s.crossProviderConsensus?.state||'').toUpperCase()==='OPPOSED')return false;
  return true;
}
async function unifiedSignals(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_SAFETY_FIRST_MARKET',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',status=String(url.searchParams.get('status')||'active').toLowerCase(),limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120))),targetActive=styleTarget(style);let rows=[];
  if(status==='active'){
    rows=(await realtimeActiveSignals(env,style)).map(x=>normalizeDisplaySignal(x,market,style)).filter(s=>publicationGateV3228(s,style));
    const seen=new Set();rows=rows.filter(s=>{const sym=canonical(s.symbol);if(!sym||seen.has(sym))return false;seen.add(sym);return true;}).sort(compareMarketOnlyQuality).slice(0,Math.min(limit,targetActive));
    if(rows.length<targetActive&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));
  }else{
    rows=(await getV31Signals(env,market,style)).map(x=>normalizeDisplaySignal(x,market,style)).filter(s=>String(s.engineVersion||'')===V3_VERSION).filter(s=>status==='all'||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  }
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_SAFETY_FIRST_MARKET',market,style,status,targetActive,activeCount:status==='active'?rows.length:undefined,atTarget:status==='active'?rows.length===targetActive:undefined,underfilled:status==='active'?rows.length<targetActive:undefined,underfillReason:status==='active'&&rows.length<targetActive?'NO_QUALIFIED_MARKET_SIGNAL_DO_NOT_FORCE_ENTRY':undefined,forcedFill:false,marketOnly:true,signals:rows});
}

'''
w=block(w,'async function unifiedSignals(url,env,ctx){','async function unifiedPerformance',signals,'app-facing publication gate')

# Status wording and policy semantics.
status=r'''async function v3Status(env,ctx){
  const portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env),missing=['SCALP','SWING'].filter(st=>Number(portfolio.styles?.[st]||0)<styleTarget(st));if(missing.length&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_SAFETY_FIRST_MARKET',service:'SignalHub Crypto safety-first MARKET-only up to 5 SCALP + 2 SWING',checkpoint:CHECKPOINT,app:V31_RELEASE,crypto:{priceAuthority:'PROVIDER_PINNED_BYBIT_PREFERRED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'UP_TO_5_MARKET_ONLY_5M_15M_1H',swing:'UP_TO_2_MARKET_ONLY_1H_4H_1D',pendingLifecycle:'DISABLED',healthMonitor:'DURABLE_OBJECT_ALARM_1S',crossProviderContextCheck:true,marketReadVersion:'V3228_SAFETY_FIRST_CURRENT_MARKET_GATE',watchMode:'STABLE100_TAP_FOR_IDEAL_PLAN'},engines:{cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},forexDisabled:true,portfolio,missingStyles:missing,missingStylesMeaning:'SEARCHING_NOT_FORCING_WEAK_ENTRY',cryptoMonitor,healthPolicy:MARKET_HEALTH_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,forcedFill:false,winRatePolicy:'STRICT_TP_SL_HISTORY_PLUS_SEPARATE_AUTO_CUT_AND_ALL_EXIT_STATS_NOT_PREDICTED_PROBABILITY'});
}

'''
w=block(w,'async function v3Status(env,ctx){','async function handleV3',status,'status')

# Android identity and quality-first messaging.
a=a.replace('APP_VERSION="3.22.7"','APP_VERSION="3.22.8"')
a=a.replace('CRYPTO • MARKET ONLY • 5 SCALP + 2 SWING','CRYPTO • SAFETY FIRST • MARKET ONLY')
a=a.replace('style+" • MARKET ONLY • "+(style.equals("SCALP")?"5 LỆNH":"2 LỆNH")','style+" • SAFETY FIRST • TỐI ĐA "+(style.equals("SCALP")?"5 LỆNH":"2 LỆNH")')
needle='content.addView(stats);content.addView(tv(performanceSummary(),9,MUTED,false));'
if needle in a:
    a=a.replace(needle,'content.addView(stats);content.addView(tv(performanceSummary(),9,MUTED,false));content.addView(tv(liveRows.size()<target?"Thiếu slot = chưa có MARKET đạt hard-safety; app không ép lệnh yếu.":"Đủ target với MARKET đã qua hard-safety.",9,liveRows.size()<target?YELLOW:GREEN,true));',1)
c=c.replace('SignalHub-Android/3.22.7','SignalHub-Android/3.22.8')
g=g.replace('versionCode 36','versionCode 37').replace("versionName '3.22.7'","versionName '3.22.8'")

worker.write_text(w);activity.write_text(a);api.write_text(c);monitor.write_text(m);gradle.write_text(g)

# Contracts
assert 'SIGNALHUB-V3-GATEWAY-3.22.8' in w
assert "const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_21';" in w
assert 'maxActiveTotal:7' in w and 'targetActiveByStyle:{SCALP:5,SWING:2}' in w
assert 'minActivePerMarket:0' in w and 'SEARCH_TO_TARGET_WITHOUT_FORCING_WEAK_MARKET_ENTRY' in w
assert 'publicationGateV3228' in w and 'NO_QUALIFIED_MARKET_SIGNAL_DO_NOT_FORCE_ENTRY' in w
assert 'QUALITY_FIRST_NO_FORCED_FILL_WITH_FINAL_PUBLICATION_GATE' in w
assert "function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?2:5;}" in w
assert 'APP_VERSION="3.22.8"' in a and 'SAFETY FIRST' in a
assert 'SignalHub-Android/3.22.8' in c
assert 'versionCode 37' in g and "versionName '3.22.8'" in g
print('patched SignalHub V3.22.8 safety-first market gate')
