from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
api=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
monitor=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
gradle=Path('signalhub-android/app/build.gradle')

w=worker.read_text(); a=activity.read_text(); c=api.read_text(); m=monitor.read_text(); g=gradle.read_text()

def block(text,start,end,replacement,name):
    i=text.find(start); assert i>=0, f'{name}: start missing'
    j=text.find(end,i); assert j>i, f'{name}: end missing'
    return text[:i]+replacement+text[j:]

# Identity.
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.7','SIGNALHUB-V3-GATEWAY-3.22.8')
w=w.replace("SIGNALHUB_V3_CHECKPOINT_20","SIGNALHUB_V3_CHECKPOINT_21")
w=w.replace("versionName: '3.22.7'","versionName: '3.22.8'")
w=w.replace("versionCode: 36,","versionCode: 37,")
w=w.replace("title: 'SignalHub 3.22.7 Market-Only Health Seven'","title: 'SignalHub 3.22.8 Hardened Market Seven'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.7-Market-Only-Health-Seven'","artifactName: 'SignalHub-Android-v3.22.8-Hardened-Market-Seven'")

# One canonical portfolio policy. No legacy 15-slot object is allowed to survive.
policy="""const PORTFOLIO_POLICY=Object.freeze({
  maxActiveTotal:7,maxActivePerMarket:7,maxActivePerStyle:5,maxNewPerScan:5,
  minActivePerMarket:0,minActivePerStyle:0,targetActivePerStyle:5,
  targetActiveByStyle:{SCALP:5,SWING:2},maxActiveByStyle:{SCALP:5,SWING:2},maxNewPerScanByStyle:{SCALP:5,SWING:2},
  maxActivePerRiskCluster:3,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,
  reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_TARGET_5_SCALP_2_SWING_MARKET_ONLY_NEVER_FORCE_WEAK',
  cryptoPendingMonitor:'DISABLED_MARKET_ONLY',cryptoHealthMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:0,
  replacementMode:'QUALITY_FIRST_RESCAN_NO_WEAK_QUOTA_FILL',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',
  stableUniverseSize:100,stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC',deepScanRotation:'FULL_QUALITY_SCAN_WHEN_UNDERFILLED',
  continuousRefill:'TARGET_5_SCALP_2_SWING_ONLY_IF_QUALIFIED',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT',forexDisabled:true
});
"""
w=block(w,'const PORTFOLIO_POLICY=Object.freeze({','function styleTarget(style)',policy,'portfolio policy')

# Conservative health policy: never retire a signal from a few noisy ticks.
health="""const MARKET_HEALTH_POLICY=Object.freeze({
  watchR:-0.38,warningR:-0.56,persistentCutR:-0.72,emergencyCutR:-0.92,
  adverseTicksForCut:18,warningTicksForCut:20,stressedCutR:-0.66,
  profitProtectStartR:1.40,profitGivebackR:0.95,
  minAgeBeforeCutMs:{SCALP:180000,SWING:900000},
  spreadStressMultiplier:2.75,liquidityStressRatio:0.48,
  action:'SIGNAL_RETIRE_ONLY_USER_CLOSES_MANUAL_POSITION',
  principle:'PERSISTENT_DETERIORATION_ONLY_NEVER_SINGLE_TICK_CUT'
});

"""
w=block(w,'const MARKET_HEALTH_POLICY=Object.freeze({','function validSignalStructure(signal){',health,'health policy')

# Rebuild candidate conversion/ranking. It evaluates a true MARKET entry at the current quote,
# not whether an old LIMIT/STOP idea happened to be close enough.
market_helpers="""function marketOnlySevenCandidate(raw){
  const s={...(raw||{})},style=String(s.style||'SCALP').toUpperCase(),side=String(s.side||'').toUpperCase(),dir=['LONG','BUY'].includes(side)?1:['SHORT','SELL'].includes(side)?-1:0;
  const read=s.marketReadV322||{},tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{},cross=String(s.crossProviderConsensus?.state||'UNAVAILABLE').toUpperCase();
  const src=Number(s.sourcePrice||s.lastPrice||0),oldEntry=Number(s.entry),oldSl=Number(s.sl),atr=Math.abs(Number(tech.atr||0)),spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),move=Math.abs(Number(tech.change24hPct||0)),ext=Math.abs(Number(tech.extensionAtr??read.extensionAtr??0)),rsi=Number(tech.rsi||50);
  if(!dir||!(src>0&&oldEntry>0&&oldSl>0)||read.hardConflict||cross==='OPPOSED')return null;
  const rule=stableUniverseRule(style),hardSpread=style==='SCALP'?Math.min(rule.maxSpread,10):Math.min(rule.maxSpread,16),hardTurnover=style==='SCALP'?Math.max(rule.minTurnover,20_000_000):Math.max(rule.minTurnover,12_000_000);
  if(!(spread>=0&&spread<=hardSpread&&turnover>=hardTurnover&&move<=(style==='SCALP'?28:38)))return null;
  if(ext>(style==='SCALP'?.55:.65))return null;
  if((dir>0&&rsi>76)||(dir<0&&rsi<24))return null;
  const contextAligned=read.contextAligned===true,contextStrong=read.contextStrong===true,execEvent=read.executionEvent===true||Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),momentum=read.executionMomentum===true;
  if(!contextAligned||!momentum)return null;
  const oldRisk=Math.abs(oldEntry-oldSl);if(!(oldRisk>0))return null;
  const driftR=Math.abs(src-oldEntry)/oldRisk;if(driftR>(style==='SCALP'?.60:.72))return null;
  const stopBuffer=Math.max(atr*(style==='SCALP'?.10:.16),src*spread/10000*1.8),sl=dir>0?Math.min(oldSl,src-stopBuffer):Math.max(oldSl,src+stopBuffer),risk=Math.abs(src-sl);if(!(risk>0))return null;
  let t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp);const minRR=style==='SCALP'?1.90:2.45;
  if(dir>0){if(!(t1>src))t1=src+risk*.95;if(!(t2>t1))t2=src+risk*1.45;if(!(t3>t2))t3=src+risk*minRR;}else{if(!(t1<src))t1=src-risk*.95;if(!(t2<t1))t2=src-risk*1.45;if(!(t3<t2))t3=src-risk*minRR;}
  const rr=Math.abs(t3-src)/risk;if(rr<minRR)return null;
  const strict=read.marketEntryReady===true&&contextStrong&&execEvent&&cross==='CONFIRMED'&&ext<=(style==='SCALP'?.24:.30);
  const strong=contextStrong&&execEvent&&cross!=='OPPOSED'&&ext<=(style==='SCALP'?.38:.45);
  const qualified=!read.hardConflict&&contextAligned&&momentum&&(execEvent||contextStrong)&&cross!=='OPPOSED';
  if(!qualified)return null;
  const tier=strict?'A_STRICT':strong?'B_STRONG':'C_QUALIFIED';
  const qualityPoints=(strict?100:strong?82:68)+(cross==='CONFIRMED'?8:cross==='NEUTRAL'?2:0)+(execEvent?6:0)+(contextStrong?6:0)+Math.max(0,6-ext*10)+Math.max(0,5-spread*.35)+Math.min(8,Math.log10(Math.max(1,turnover/1e6))*2)+Math.min(7,rr);
  return {...s,orderType:'MARKET',entry:src,actualEntry:src,sl:Number(sl.toPrecision(10)),tp1:Number(t1.toPrecision(10)),tp2:Number(t2.toPrecision(10)),tp3:Number(t3.toPrecision(10)),tp:Number(t3.toPrecision(10)),status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',targetRR:Number(rr.toFixed(3)),coverageFallback:false,marketOnly:true,marketOnlyQuality:tier,qualityPoints:Number(qualityPoints.toFixed(3)),marketOnlyFacts:{tier,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:momentum,crossProvider:cross,extensionAtr:Number(ext.toFixed(3)),driftR:Number(driftR.toFixed(3)),spreadBps:spread,turnover24h:turnover,targetRR:Number(rr.toFixed(3))},entryAssessment:{verdict:'PASS',method:'V3228_TRUE_MARKET_ENTRY_HARD_SAFETY_RANKING',failed:[]}};
}
function compareMarketOnlyQuality(a,b){
  const tier={A_STRICT:0,B_STRONG:1,C_QUALIFIED:2},ta=tier[a.marketOnlyQuality]??9,tb=tier[b.marketOnlyQuality]??9;if(ta!==tb)return ta-tb;
  if(Number(a.qualityPoints||0)!==Number(b.qualityPoints||0))return Number(b.qualityPoints||0)-Number(a.qualityPoints||0);
  const af=a.marketOnlyFacts||{},bf=b.marketOnlyFacts||{};if(Number(af.spreadBps)!==Number(bf.spreadBps))return Number(af.spreadBps)-Number(bf.spreadBps);if(Number(af.extensionAtr)!==Number(bf.extensionAtr))return Number(af.extensionAtr)-Number(bf.extensionAtr);return Number(bf.turnover24h||0)-Number(af.turnover24h||0);
}

"""
w=block(w,'function marketOnlySevenCandidate(raw){','function setupPriority(s){',market_helpers,'market candidate')

# Scan the entire eligible Stable100 when underfilled. This increases the chance of filling 5+2
# without weakening the safety gate. It explicitly reports quality shortage instead of forcing a bad entry.
scan="""async function scanCrypto(env,style){
  style=String(style||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const trackerEvents=await retireAllLegacyActiveSignals(env),snap=await loadCryptoSnapshot(env);if(snap.live===false)return {ok:true,version:V3_VERSION,market:'CRYPTO',style,status:'NO_FRESH_CRYPTO_SNAPSHOT',created:0,provider:snap.provider,live:false,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};
  const all=snap.rows,stable100=await persistStable100(env,snap,all),portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style),liquid=stable100.filter(x=>stableUniverseEligible(x,style));
  const rankedLimit=styleUnderfilled?liquid.length:Math.min(style==='SCALP'?60:50,liquid.length),ranked=rotatingStableCandidates(liquid,style,rankedLimit),rawAnalyses=await analyzeCryptoBatch(ranked,style,8),marketCandidates=rawAnalyses.map(marketOnlySevenCandidate).filter(Boolean).sort(compareMarketOnlyQuality),created=await maybeCreateV31(env,'CRYPTO',style,marketCandidates),after=await realtimePortfolioSnapshot(env),activeAfter=Number(after.styles?.[style]||0),target=styleTarget(style);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_HARDENED_MARKET_ONLY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:marketCandidates.length,strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='A_STRICT').length,strong:marketCandidates.filter(x=>x.marketOnlyQuality==='B_STRONG').length,qualified:marketCandidates.filter(x=>x.marketOnlyQuality==='C_QUALIFIED').length,created:created.length,newSignals:created,activeAfter,targetActive:target,exactTarget:activeAfter===target,qualityShortage:activeAfter<target,marketOnly:true,standby:{disabled:true,count:0},trackerEvents,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:activeAfter<target?'Không ép đủ quota khi thị trường thiếu setup đạt hard-safety. Scanner đã quét toàn bộ universe đủ điều kiện.':'Đủ target bằng MARKET setup đạt hard-safety.'};
}

"""
w=block(w,'async function scanCrypto(env,style){','async function cryptoOnlyMaintenance(env){',scan,'scan crypto')

# Status terminology: target, never forced.
w=w.replace("service:'SignalHub Crypto MARKET-only 5 SCALP + 2 SWING'","service:'SignalHub Crypto hardened MARKET-only target 5 SCALP + 2 SWING'")
w=w.replace("marketReadVersion:'V3227_MARKET_ONLY_STRUCTURE_CONTEXT_LIQUIDITY'","marketReadVersion:'V3228_TRUE_MARKET_HARD_SAFETY_RANKING'")
w=w.replace("winRatePolicy:'STRICT_TP_SL_HISTORY_PLUS_SEPARATE_AUTO_CUT_AND_ALL_EXIT_STATS_NOT_PREDICTED_PROBABILITY'","winRatePolicy:'STRICT_TP_SL_HISTORY_PLUS_SEPARATE_AUTO_CUT; NEVER_PREDICTED_WIN_PROBABILITY'")

# Android identity and explicit quality-shortage semantics.
a=a.replace('APP_VERSION="3.22.7"','APP_VERSION="3.22.8"')
a=a.replace('MARKET ONLY • 5 SCALP + 2 SWING','HARDENED MARKET • TARGET 5 SCALP + 2 SWING')
a=a.replace('CRYPTO • MARKET ONLY • 5 SCALP + 2 SWING','CRYPTO • HARDENED MARKET • TARGET 5 + 2')
c=c.replace('SignalHub-Android/3.22.7','SignalHub-Android/3.22.8')
g=g.replace('versionCode 36','versionCode 37').replace("versionName '3.22.7'","versionName '3.22.8'")

worker.write_text(w);activity.write_text(a);api.write_text(c);monitor.write_text(m);gradle.write_text(g)

assert 'SIGNALHUB-V3-GATEWAY-3.22.8' in w
assert 'maxActiveTotal:7' in w and 'targetActiveByStyle:{SCALP:5,SWING:2}' in w
assert 'CRYPTO_TARGET_5_SCALP_2_SWING_MARKET_ONLY_NEVER_FORCE_WEAK' in w
assert 'V3228_TRUE_MARKET_ENTRY_HARD_SAFETY_RANKING' in w
assert 'qualityShortage' in w
assert 'versionCode 37' in g and "versionName '3.22.8'" in g
print('patched SignalHub V3.22.8 hardened market seven')
