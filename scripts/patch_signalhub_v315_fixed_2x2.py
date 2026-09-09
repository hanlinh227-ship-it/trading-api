from pathlib import Path

P=Path('signalhub-worker/gateway-v3.js')
s=P.read_text()

def rep(old,new,label):
    global s
    if old not in s:
        raise SystemExit(f'{label}: marker missing')
    s=s.replace(old,new,1)

rep("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.14.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.15.0';",'version')
rep("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_06';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_07';",'checkpoint')
rep("entryAssessment:'V314_CRYPTO_EVIDENCE_CHECKS_NO_NUMERIC_SCORE',","entryAssessment:'V315_FIXED_2X2_HARD_SAFETY',",'policy assessment')
rep("portfolioPolicy:{maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE_QUALITY_FIRST',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true}","portfolioPolicy:{maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:2,minActivePerStyle:2,targetActivePerStyle:2,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_FIXED_2X2_STRICT_THEN_CONDITIONAL',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true}",'top policy')
rep("const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE_QUALITY_FIRST',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true});","const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:2,minActivePerStyle:2,targetActivePerStyle:2,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_FIXED_2X2_STRICT_THEN_CONDITIONAL',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true});",'runtime policy')

rep("  let dir=0,regime='NO_TRADE',story='',reclaimed=false,displacement=false,liquidityEvent=false;","  let dir=0,regime='NO_TRADE',story='',reclaimed=false,displacement=false,liquidityEvent=false,coverageFallback=false;",'fallback flag')

rep("    else if(htf===-1&&breakoutDown){dir=-1;regime='HTF_BREAKOUT_CONFIRMATION';story='H4/D1 bearish + H1 displacement confirms breakdown';reclaimed=a.bosDown;displacement=true;}\n    else return null;","    else if(htf===-1&&breakoutDown){dir=-1;regime='HTF_BREAKOUT_CONFIRMATION';story='H4/D1 bearish + H1 displacement confirms breakdown';reclaimed=a.bosDown;displacement=true;}\n    else{\n      const vote=Number(c.trend||0)*3+Number(b.trend||0)*2+Number(a.trend||0)+Number(b.momentum||0)+Number(a.momentum||0);\n      dir=vote>0?1:vote<0?-1:(px>=Number(b.ema20||px)?1:-1);\n      regime='HTF_COVERAGE_CONDITIONAL';story='Best-available H4/D1 context; wait for a conditional pending trigger instead of forcing a market entry';coverageFallback=true;\n    }",'swing fallback')

rep("    else if(breakoutDown&&b.trend===-1&&c.trend!==1){dir=-1;regime='BREAKOUT_CONFIRMATION';story='5m displacement at breakdown edge + bearish 15m context';reclaimed=a.bosDown;displacement=true;}\n    else return null;","    else if(breakoutDown&&b.trend===-1&&c.trend!==1){dir=-1;regime='BREAKOUT_CONFIRMATION';story='5m displacement at breakdown edge + bearish 15m context';reclaimed=a.bosDown;displacement=true;}\n    else{\n      const vote=Number(c.trend||0)*2+Number(b.trend||0)*2+Number(a.trend||0)+Number(a.momentum||0)+Number(b.momentum||0);\n      dir=vote>0?1:vote<0?-1:(px>=Number(a.ema20||px)?1:-1);\n      regime='MICRO_COVERAGE_CONDITIONAL';story='Best-available 5m/15m/1h context; wait for a conditional pending trigger instead of forcing a market entry';coverageFallback=true;\n    }",'scalp fallback')

rep("  let orderType='MARKET',entry=px,entryModel=liquidityEvent?'SWEEP_RECLAIM_MARKET':'CONFIRMED_STRUCTURE_MARKET';\n  if(regime.includes('BREAKOUT')){orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='CONFIRMED_BREAKOUT_TRIGGER';}\n  else if(!liquidityEvent&&(tooExtended||badMarketLocation||regime.includes('RECLAIM'))){","  let orderType='MARKET',entry=px,entryModel=liquidityEvent?'SWEEP_RECLAIM_MARKET':'CONFIRMED_STRUCTURE_MARKET';\n  if(coverageFallback){\n    const raw=dir>0?Math.max(a.ema20,a.recentLow+.34*atr1):Math.min(a.ema20,a.recentHigh-.34*atr1);\n    if((dir>0&&raw<px-entryBuffer*.20)||(dir<0&&raw>px+entryBuffer*.20)){orderType='LIMIT';entry=raw;entryModel='COVERAGE_PULLBACK_TRIGGER';}\n    else{orderType='STOP';entry=dir>0?Math.max(a.priorHigh,a.recentHigh)+entryBuffer:Math.min(a.priorLow,a.recentLow)-entryBuffer;entryModel='COVERAGE_BREAKOUT_TRIGGER';}\n  }else if(regime.includes('BREAKOUT')){orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='CONFIRMED_BREAKOUT_TRIGGER';}\n  else if(!liquidityEvent&&(tooExtended||badMarketLocation||regime.includes('RECLAIM'))){",'coverage routing')

rep("  if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;","  if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0))return null;if(risk>maxRisk){if(!coverageFallback)return null;risk=maxRisk;sl=entry-dir*risk;}",'coverage risk clamp')

rep("  const qualityEvidence={contextAligned:true,liquidityEvent,displacementConfirmed:displacement,structureReclaimed:reclaimed,secondaryProviderConfirmed:false,entryNotChasing:orderType!=='MARKET'||!tooExtended,invalidationStructural:Number.isFinite(anchor),targetPathClear:dir>0?sl<entry&&entry<tp1&&tp1<tp2&&tp2<tp3:sl>entry&&entry>tp1&&tp1>tp2&&tp2>tp3};\n  const judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • EVIDENCE CONFIRMED`;\n  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cluster,marketRegime:regime,marketStory:story,judgment,entryModel,slModel:'STRUCTURE_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:spreadState,qualityEvidence,technicalAtIssue:","  const qualityEvidence={contextAligned:true,liquidityEvent,displacementConfirmed:displacement,structureReclaimed:reclaimed,secondaryProviderConfirmed:false,entryNotChasing:orderType!=='MARKET'||!tooExtended,invalidationStructural:Number.isFinite(anchor),targetPathClear:dir>0?sl<entry&&entry<tp1&&tp1<tp2&&tp2<tp3:sl>entry&&entry>tp1&&tp1>tp2&&tp2>tp3,coverageConditional:coverageFallback};\n  const judgment=coverageFallback?`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • CONDITIONAL COVERAGE`:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • EVIDENCE CONFIRMED`;\n  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cluster,marketRegime:regime,marketStory:story,judgment,entryModel,coverageFallback,coverageTier:coverageFallback?'BEST_AVAILABLE_CONDITIONAL':'STRICT_CONFIRMED',slModel:'STRUCTURE_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:spreadState,qualityEvidence,technicalAtIssue:",'coverage metadata')

needle="""function setupPriority(s){
"""
coverage_fn="""function assessCoverageSetup(raw){
  const s=raw||{},dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{};
  const style=String(s.style||'SCALP').toUpperCase(),order=String(s.orderType||'').toUpperCase(),risk=Math.abs(entry-sl),triggerDistance=risk>0&&src>0?Math.abs(src-entry)/risk:999;
  const targetPath=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3;
  const entryLocation=order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false;
  const spread=Number(tech.spreadBps||0),turnover=Number(tech.turnover24h||0);
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',pendingOnly:['LIMIT','STOP'].includes(order),structure:validSignalStructure(s),cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===(style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE'),liveSource:src>0,entryLocation,pendingReachable:triggerDistance<=(style==='SWING'?1.80:1.40),invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadHard:spread>=0&&spread<=(style==='SWING'?18:8),liquidityHard:turnover>=(style==='SWING'?10_000_000:20_000_000)};
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'V315_FIXED_2X2_HARD_SAFETY',tier:'BEST_AVAILABLE_CONDITIONAL',checks,failed,executionFacts:{triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}};
}
"""
if needle not in s: raise SystemExit('coverage function anchor missing')
s=s.replace(needle,coverage_fn+needle,1)

old="""  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(x=>{const assessment=assessEntrySetup(x);return {...x,entryAssessment:assessment};}).filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
"""
new="""  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(x=>{const strict=assessEntrySetup(x);if(strict.verdict==='PASS')return {...x,coverageTier:'STRICT_CONFIRMED',entryAssessment:strict};const fallback=Boolean(x.coverageFallback)?assessCoverageSetup(x):strict;return {...x,entryAssessment:fallback};}).filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
"""
rep(old,new,'candidate admission')
rep("const issuedAt=nowIso(),id=`V314-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;","const issuedAt=nowIso(),id=`V315-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;",'signal id')

old_scan="""  const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleEmpty=Number(portfolio.styles?.[style]||0)<PORTFOLIO_POLICY.minActivePerStyle;
  const rankedLimit=style==='SCALP'?(styleEmpty?20:14):(styleEmpty?18:12),minTurnover=style==='SCALP'?20_000_000:10_000_000,maxSpread=style==='SCALP'?8:18;
  const liquid=all.filter(x=>Number(x.lastPrice)>0&&Number(x.turnover24h||0)>=minTurnover&&(x.spreadBps==null||Number(x.spreadBps)<=maxSpread));
  const ranked=liquid.sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,rankedLimit);
  const rawAnalyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean),assessed=rawAnalyses.map(x=>({...x,entryAssessment:assessEntrySetup(x)})),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.14 crypto stability engine: confirmation-first SCALP/SWING, secondary-provider evidence and cluster concentration control. No predicted win-rate or numeric setup score.'};
"""
new_scan="""  const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<PORTFOLIO_POLICY.targetActivePerStyle;
  const rankedLimit=style==='SCALP'?(styleUnderfilled?30:14):(styleUnderfilled?26:12),minTurnover=style==='SCALP'?20_000_000:10_000_000,maxSpread=style==='SCALP'?8:18;
  const liquid=all.filter(x=>Number(x.lastPrice)>0&&Number(x.turnover24h||0)>=minTurnover&&(x.spreadBps==null||Number(x.spreadBps)<=maxSpread));
  const ranked=liquid.sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,rankedLimit);
  const rawAnalyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean),assessed=rawAnalyses.map(x=>{const strict=assessEntrySetup(x);const assessment=strict.verdict==='PASS'?strict:(x.coverageFallback?assessCoverageSetup(x):strict);return {...x,entryAssessment:assessment};}),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.15 fixed 2x2 book: strict setups are preferred; if a style would fall below two active ideas, best-available conditional LIMIT/STOP setups may fill coverage slots while hard structure, liquidity, spread, invalidation and target-path checks remain mandatory.'};
"""
rep(old_scan,new_scan,'scan crypto')

old_unified="""  if(status==='active'&&rows.length===0&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(scanCrypto(env,style)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
"""
new_unified="""  if(status==='active'&&rows.length<PORTFOLIO_POLICY.targetActivePerStyle){
    await scanCrypto(env,style).catch(()=>{});
    let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));
    rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);
  }
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,targetActive:PORTFOLIO_POLICY.targetActivePerStyle,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
"""
rep(old_unified,new_unified,'active refill response')

rep("async function v314Stability(env){","async function v315Stability(env){",'stability name')
rep("if(url.pathname==='/v3/stability'&&req.method==='GET')return v314Stability(env);","if(url.pathname==='/v3/stability'&&req.method==='GET')return v315Stability(env);",'stability route')
rep("service:'SignalHub Crypto Stability SCALP/SWING gateway'","service:'SignalHub Crypto Fixed 2x2 SCALP/SWING gateway'",'status service')
rep("scalp:'CONFIRMATION_FIRST_5M_15M_1H',swing:'HTF_CONFIRMED_1H_4H_1D'","scalp:'FIXED_2_ACTIVE_STRICT_THEN_CONDITIONAL_5M_15M_1H',swing:'FIXED_2_ACTIVE_STRICT_THEN_CONDITIONAL_1H_4H_1D'",'status mode')

P.write_text(s)

checkpoint=Path('SIGNALHUB_V3_CHECKPOINT_07_FIXED_2X2.md')
checkpoint.write_text('''# SignalHub V3 Checkpoint 07 — Fixed 2x2 Crypto Book\n\n- Backend version: SIGNALHUB-V3-GATEWAY-3.15.0\n- Crypto only; Forex remains disabled.\n- Portfolio target: exactly 2 active SCALP ideas + 2 active SWING ideas whenever live provider data is available.\n- Strict confirmed setups are always ranked first.\n- If a style is underfilled, best-available conditional coverage is allowed only as LIMIT/STOP, never forced MARKET.\n- Conditional coverage still requires hard checks: valid Entry/SL/TP geometry, structural invalidation, live source price, correct pending side, reachable trigger, liquidity, spread and target path.\n- One active idea per symbol across styles remains enforced.\n- Meme concentration remains capped at one active idea.\n- Active API synchronously attempts refill when a style has fewer than 2 ideas.\n- Cron/status/monitor maintenance also refill underfilled styles.\n- Historical win rate remains closed TP/SL only and is not a predicted probability.\n\nThe 2x2 occupancy target is a portfolio availability rule, not a claim that all four ideas have identical conviction. Conditional coverage is explicitly labeled BEST_AVAILABLE_CONDITIONAL.\n''')
print('patched SignalHub V3.15 fixed 2x2 coverage')
