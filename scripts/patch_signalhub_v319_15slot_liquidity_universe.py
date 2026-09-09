from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text(); a=A.read_text(); g=G.read_text()

def must_replace(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing {label}: {old[:120]}')
    return text.replace(old,new)

# -----------------------------------------------------------------------------
# Version / release metadata
# -----------------------------------------------------------------------------
w=must_replace(w,"const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.16.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.19.0';",'worker version')
w=must_replace(w,"const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_07';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_10';",'checkpoint')
w=must_replace(w,"versionCode: 21,\n  versionName: '3.16.0',\n  title: 'SignalHub 3.16.0 Fixed 2x2 + Watchlist',","versionCode: 24,\n  versionName: '3.19.0',\n  title: 'SignalHub 3.19.0 10 Scalp + 5 Swing Stable Universe',",'release meta')
w=must_replace(w,"artifactName: 'SignalHub-Android-v3.16.0-Fixed-2x2-Watchlist',","artifactName: 'SignalHub-Android-v3.19.0-10Scalp-5Swing-StableUniverse',",'artifact')
w=must_replace(w,"'V3.16 adds a read-only Watchlist analyzer for user-selected crypto symbols; Watchlist analysis never consumes the fixed 2 SCALP + 2 SWING active book.',","'V3.19 targets exactly 10 SCALP + 5 SWING active reference signals, counting both OPEN market entries and PENDING LIMIT/STOP entries.',\n    'V3.19 filters the trading universe for strong turnover, tight spread, sane daily movement/funding and usable open interest when available; weak-liquidity symbols do not consume the 15 reference slots.',\n    'V3.19 refreshes the full live perpetual universe every maintenance cycle and keeps larger style-specific hot-spare pools so stronger new candidates can replace invalidated, closed or stale pending ideas.',\n    'V3.18 fixes Watchlist keyboard/focus and adds live symbol suggestions. Watchlist remains read-only and never consumes the 15 active reference slots.',",'release notes')

# -----------------------------------------------------------------------------
# Policy: 10 SCALP + 5 SWING, exact 15 total, one symbol across styles.
# -----------------------------------------------------------------------------
old_policy="portfolioPolicy:{maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:2,minActivePerStyle:2,targetActivePerStyle:2,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_FIXED_2X2_STRICT_THEN_CONDITIONAL',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:3,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',forexDisabled:true}"
new_policy="portfolioPolicy:{maxActiveTotal:15,maxActivePerMarket:15,maxActivePerStyle:10,maxNewPerScan:10,minActivePerStyle:5,targetActivePerStyle:10,targetActiveByStyle:{SCALP:10,SWING:5},maxActiveByStyle:{SCALP:10,SWING:5},maxNewPerScanByStyle:{SCALP:10,SWING:5},maxActivePerRiskCluster:5,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_EXACT_10_SCALP_5_SWING_STABLE_LIQUID_UNIVERSE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:12,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'FULL_LIVE_PROVIDER_SNAPSHOT_EVERY_CRON_AND_REFILL',forexDisabled:true}"
w=must_replace(w,old_policy,new_policy,'decision embedded portfolio policy')
old_global="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:2,minActivePerStyle:2,targetActivePerStyle:2,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_FIXED_2X2_STRICT_THEN_CONDITIONAL',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:3,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',forexDisabled:true});"
new_global="""const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:15,maxActivePerMarket:15,maxActivePerStyle:10,maxNewPerScan:10,minActivePerStyle:5,targetActivePerStyle:10,targetActiveByStyle:{SCALP:10,SWING:5},maxActiveByStyle:{SCALP:10,SWING:5},maxNewPerScanByStyle:{SCALP:10,SWING:5},maxActivePerRiskCluster:5,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_EXACT_10_SCALP_5_SWING_STABLE_LIQUID_UNIVERSE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:12,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL',universeRefresh:'FULL_LIVE_PROVIDER_SNAPSHOT_EVERY_CRON_AND_REFILL',forexDisabled:true});
function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?5:10;}
function styleMax(style){return styleTarget(style);}
function styleNewLimit(style){return styleTarget(style);}
const STABLE_BASE_EXCLUDE=new Set(['USDC','USDE','FDUSD','DAI','TUSD','USDP','BUSD','EUR','EURC','PYUSD']);
function stableUniverseRule(style){return String(style||'').toUpperCase()==='SWING'?{minTurnover:35_000_000,maxSpread:12,maxMove:30,minOi:3_000_000,maxFunding:.005}:{minTurnover:50_000_000,maxSpread:6,maxMove:22,minOi:5_000_000,maxFunding:.003};}
function stableUniverseEligible(t,style){
  if(!t||!(Number(t.lastPrice)>0))return false;const symbol=canonical(t.symbol),base=symbol.replace(/USDT$/,''),r=stableUniverseRule(style),turn=Number(t.turnover24h||0),spread=t.spreadBps==null?999:Number(t.spreadBps),move=Math.abs(Number(t.change24hPct||0)),oi=t.openInterestValue==null?null:Number(t.openInterestValue),fund=t.fundingRate==null?null:Math.abs(Number(t.fundingRate));
  if(!symbol.endsWith('USDT')||STABLE_BASE_EXCLUDE.has(base))return false;if(!(turn>=r.minTurnover)||!(spread>=0&&spread<=r.maxSpread)||move>r.maxMove)return false;if(oi!=null&&Number.isFinite(oi)&&oi>0&&oi<r.minOi)return false;if(fund!=null&&Number.isFinite(fund)&&fund>r.maxFunding)return false;return true;
}
function stableUniverseCompare(a,b){const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;const am=Math.abs(Number(a.change24hPct||0)),bm=Math.abs(Number(b.change24hPct||0));if(am!==bm)return am-bm;return Number(b.turnover24h||0)-Number(a.turnover24h||0);}
function signalLiquidityFacts(s){const t=s?.technicalAtIssue||{};return {turnover:Number(t.turnover24h||0),spread:Number(t.spreadBps??999),move:Math.abs(Number(t.change24hPct||0)),oi:t.openInterestValue==null?null:Number(t.openInterestValue),funding:t.fundingRate==null?null:Math.abs(Number(t.fundingRate))};}
"""
w=must_replace(w,old_global,new_global,'global portfolio policy')

# Durable Object reservation and standby promotion must use style-specific caps/targets.
w=must_replace(w,"if(active.filter(x=>String(x.style||'').toUpperCase()===style).length>=policy.maxActivePerStyle)return reject('MAX_ACTIVE_STYLE');","if(active.filter(x=>String(x.style||'').toUpperCase()===style).length>=styleMax(style))return reject('MAX_ACTIVE_STYLE');",'register style cap')
w=must_replace(w,"while(styleCount<Number(PORTFOLIO_POLICY.targetActivePerStyle||2)&&pool.length){","while(styleCount<styleTarget(style)&&pool.length){",'standby target')
w=must_replace(w,"if(active.length>=PORTFOLIO_POLICY.maxActiveTotal||active.filter(x=>String(x.style||'').toUpperCase()===style).length>=PORTFOLIO_POLICY.maxActivePerStyle)break;","if(active.length>=PORTFOLIO_POLICY.maxActiveTotal||active.filter(x=>String(x.style||'').toUpperCase()===style).length>=styleMax(style))break;",'standby cap')
w=w.replace('id=`V3152R-CRYPTO-${style}-${symbol}-${Date.now().toString(36)}`','id=`V319R-CRYPTO-${style}-${symbol}-${Date.now().toString(36)}`')

# Pending ideas are intentionally refreshed. Old unfilled ideas should not block stronger fresh candidates forever.
old_pending="""const trigger=type==='LIMIT'?(dir>0?entryPx<=entry:entryPx>=entry):type==='STOP'?(dir>0?entryPx>=entry:entryPx<=entry):false;
        const structureInvalidation=Number(s.invalidationLevel||sl),invalidated=dir>0?exitPx<=structureInvalidation:exitPx>=structureInvalidation;
        const missedMove=type==='LIMIT'&&tp1>0&&(dir>0?exitPx>=tp1:exitPx<=tp1);
        if(invalidated||missedMove){
          s.status='CANCELLED';s.lifecycle=invalidated?'INVALIDATED_BEFORE_ENTRY':'MISSED_MOVE_BEFORE_ENTRY';s.entryState='CANCELLED';s.cancelledAt=at;s.outcome=s.lifecycle;s.resolution='REALTIME_PENDING_INVALIDATION';eventType='CANCELLED';mutated=true;delete reg[id];dirty=true;
        }else if(trigger){"""
new_pending="""const trigger=type==='LIMIT'?(dir>0?entryPx<=entry:entryPx>=entry):type==='STOP'?(dir>0?entryPx>=entry:entryPx<=entry):false;
        const structureInvalidation=Number(s.invalidationLevel||sl),invalidated=dir>0?exitPx<=structureInvalidation:exitPx>=structureInvalidation;
        const missedMove=type==='LIMIT'&&tp1>0&&(dir>0?exitPx>=tp1:exitPx<=tp1);
        const issued=Date.parse(s.issuedAt||s.standbyPreparedAt||''),pendingAge=Number.isFinite(issued)?Math.max(0,Date.now()-issued):0,maxPendingAge=String(s.style||'').toUpperCase()==='SWING'?6*60*60*1000:20*60*1000;
        const stalePending=pendingAge>maxPendingAge;
        const qTurn=Number(q.turnover24h||s?.technicalAtIssue?.turnover24h||0),qSpread=Number(q.spreadBps??s?.technicalAtIssue?.spreadBps??999),rule=stableUniverseRule(s.style),liquidityDegraded=qTurn<rule.minTurnover||qSpread>rule.maxSpread*1.35;
        if(invalidated||missedMove||stalePending||liquidityDegraded){
          s.status='CANCELLED';s.lifecycle=invalidated?'INVALIDATED_BEFORE_ENTRY':missedMove?'MISSED_MOVE_BEFORE_ENTRY':stalePending?'STALE_PENDING_REFRESH':'LIQUIDITY_DEGRADED_BEFORE_ENTRY';s.entryState='CANCELLED';s.cancelledAt=at;s.outcome=s.lifecycle;s.resolution='REALTIME_PENDING_INVALIDATION_REFRESH';eventType='CANCELLED';mutated=true;delete reg[id];dirty=true;
        }else if(trigger){"""
w=must_replace(w,old_pending,new_pending,'pending refresh')

# Include stability facts in each setup so both strict and conditional paths can enforce them.
old_tech="spreadBps:spread,turnover24h:Number(t.turnover24h||0),sweepHigh:a.sweepHigh"
new_tech="spreadBps:spread,turnover24h:Number(t.turnover24h||0),change24hPct:Number(t.change24hPct||0),openInterestValue:t.openInterestValue==null?null:Number(t.openInterestValue),fundingRate:t.fundingRate==null?null:Number(t.fundingRate),sweepHigh:a.sweepHigh"
w=must_replace(w,old_tech,new_tech,'technical liquidity facts')

# Strict entry assessment: quality remains structural, but weak/fragile market microstructure is a hard NO TRADE.
old_strict="""const spread=Number(tech.spreadBps||0),turnover=Number(tech.turnover24h||0),rsi=Number(tech.rsi||50),spreadQuality=spread>=0&&spread<=(style==='SWING'?16:7),liquidityQuality=turnover>=(style==='SWING'?10_000_000:20_000_000),momentumSanity=dir>0?rsi<=70:rsi>=30;
  const confirmationStory=regime.includes('SWEEP')||regime.includes('RECLAIM')||regime.includes('CONFIRMATION'),displacementOrLiquidity=Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),structureEvidence=Boolean(ev.structureReclaimed)||Boolean(ev.liquidityEvent)||regime.includes('BREAKOUT');
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===expectedStyle,contextAligned,confirmationStory,displacementOrLiquidity,structureEvidence,secondaryProvider:s.crossProviderConfirmation===true,entryLocation:src>0&&marketLocation,pendingReachable,invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadQuality,liquidityQuality,momentumSanity,executionConditions:String(s.executionCaution||'NORMAL').toUpperCase()!=='WIDE',liveSource:src>0};"""
new_strict="""const spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),rsi=Number(tech.rsi||50),rule=stableUniverseRule(style),move=Math.abs(Number(tech.change24hPct||0)),oi=tech.openInterestValue==null?null:Number(tech.openInterestValue),funding=tech.fundingRate==null?null:Math.abs(Number(tech.fundingRate)),spreadQuality=spread>=0&&spread<=rule.maxSpread,liquidityQuality=turnover>=rule.minTurnover,dailyMoveSanity=move<=rule.maxMove,openInterestSanity=oi==null||!Number.isFinite(oi)||oi<=0||oi>=rule.minOi,fundingSanity=funding==null||!Number.isFinite(funding)||funding<=rule.maxFunding,momentumSanity=dir>0?rsi<=70:rsi>=30;
  const confirmationStory=regime.includes('SWEEP')||regime.includes('RECLAIM')||regime.includes('CONFIRMATION'),displacementOrLiquidity=Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),structureEvidence=Boolean(ev.structureReclaimed)||Boolean(ev.liquidityEvent)||regime.includes('BREAKOUT');
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===expectedStyle,contextAligned,confirmationStory,displacementOrLiquidity,structureEvidence,secondaryProvider:s.crossProviderConfirmation===true,entryLocation:src>0&&marketLocation,pendingReachable,invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadQuality,liquidityQuality,dailyMoveSanity,openInterestSanity,fundingSanity,momentumSanity,executionConditions:String(s.executionCaution||'NORMAL').toUpperCase()!=='WIDE',liveSource:src>0};"""
w=must_replace(w,old_strict,new_strict,'strict liquidity assessment')
w=w.replace("method:'V314_CRYPTO_EVIDENCE_CHECKS_NO_NUMERIC_SCORE'","method:'V319_CRYPTO_STABLE_LIQUIDITY_STRUCTURE_CHECKS_NO_NUMERIC_SCORE'")
w=w.replace("executionFacts:{extensionAtr:Number(ext.toFixed(3)),triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}","executionFacts:{extensionAtr:Number(ext.toFixed(3)),triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,change24hPct:move,openInterestValue:oi,fundingAbs:funding,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}")

# Conditional reserve assessment uses the same stable-liquidity floor. It may be conditional on entry, never conditional on weak liquidity.
old_cov="""const spread=Number(tech.spreadBps||0),turnover=Number(tech.turnover24h||0);
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',pendingOnly:['LIMIT','STOP'].includes(order),structure:validSignalStructure(s),cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===(style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE'),liveSource:src>0,entryLocation,pendingReachable:triggerDistance<=(style==='SWING'?1.80:1.40),invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadHard:spread>=0&&spread<=(style==='SWING'?18:8),liquidityHard:turnover>=(style==='SWING'?10_000_000:20_000_000)};
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'V315_FIXED_2X2_HARD_SAFETY',tier:'BEST_AVAILABLE_CONDITIONAL',checks,failed,executionFacts:{triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}};"""
new_cov="""const spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),rule=stableUniverseRule(style),move=Math.abs(Number(tech.change24hPct||0)),oi=tech.openInterestValue==null?null:Number(tech.openInterestValue),funding=tech.fundingRate==null?null:Math.abs(Number(tech.fundingRate));
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',pendingOnly:['LIMIT','STOP'].includes(order),structure:validSignalStructure(s),cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===(style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE'),liveSource:src>0,entryLocation,pendingReachable:triggerDistance<=(style==='SWING'?1.80:1.40),invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadHard:spread>=0&&spread<=rule.maxSpread,liquidityHard:turnover>=rule.minTurnover,dailyMoveHard:move<=rule.maxMove,openInterestHard:oi==null||!Number.isFinite(oi)||oi<=0||oi>=rule.minOi,fundingHard:funding==null||!Number.isFinite(funding)||funding<=rule.maxFunding};
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'V319_STABLE_LIQUIDITY_CONDITIONAL_HARD_SAFETY',tier:'BEST_AVAILABLE_CONDITIONAL',checks,failed,executionFacts:{triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,change24hPct:move,openInterestValue:oi,fundingAbs:funding,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}};"""
w=must_replace(w,old_cov,new_cov,'coverage liquidity assessment')

# Prioritize structurally good candidates but among those prefer tighter spread, calmer move and deeper turnover/OI.
old_priority="""function setupPriority(s){
  const r=String(s.marketRegime||''),family=r.includes('LIQUIDITY')?0:r.includes('RECLAIM')?1:r.includes('BREAKOUT')?2:r.includes('CONTINUATION')?3:4,spread=Number(s?.technicalAtIssue?.spreadBps||999),ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),turnover=Number(s?.technicalAtIssue?.turnover24h||0);
  return [family,spread,ext,-turnover];
}"""
new_priority="""function setupPriority(s){
  const r=String(s.marketRegime||''),family=r.includes('LIQUIDITY')?0:r.includes('RECLAIM')?1:r.includes('BREAKOUT')?2:r.includes('CONTINUATION')?3:4,spread=Number(s?.technicalAtIssue?.spreadBps??999),ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),move=Math.abs(Number(s?.technicalAtIssue?.change24hPct||0)),turnover=Number(s?.technicalAtIssue?.turnover24h||0),oi=Number(s?.technicalAtIssue?.openInterestValue||0);
  return [family,spread,ext,move,-turnover,-oi];
}"""
w=must_replace(w,old_priority,new_priority,'setup priority')

# Candidate analysis is concurrency-limited to avoid provider bursts as the quality universe expands.
needle="async function analyzeCryptoCandidate(t,style){"
idx=w.index(needle)
end=w.index("\n\nfunction v31Prefix",idx)
block=w[idx:end]
if 'analyzeCryptoBatch' not in w:
    w=w[:end]+"""
async function analyzeCryptoBatch(rows,style,concurrency=6){
  const out=new Array(rows.length);let next=0;async function worker(){while(true){const i=next++;if(i>=rows.length)return;out[i]=await analyzeCryptoCandidate(rows[i],style);}}const n=Math.max(1,Math.min(concurrency,rows.length||1));await Promise.all(Array.from({length:n},()=>worker()));return out.filter(Boolean);
}
"""+w[end:]

# maybeCreate uses style-specific target/cap and can refill the whole requested style in one scan.
w=must_replace(w,"if(made.length>=PORTFOLIO_POLICY.maxNewPerScan||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||marketCount()>=PORTFOLIO_POLICY.maxActivePerMarket||styleCount()>=PORTFOLIO_POLICY.maxActivePerStyle)break;","if(made.length>=styleNewLimit(style)||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||marketCount()>=PORTFOLIO_POLICY.maxActivePerMarket||styleCount()>=styleMax(style))break;",'maybeCreate style caps')
w=w.replace('id=`V315-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`','id=`V319-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`')

# Full live-universe refresh, strong-liquidity prefilter, wider discovery when a style is under target.
old_scan="""const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<PORTFOLIO_POLICY.targetActivePerStyle;
  const rankedLimit=style==='SCALP'?(styleUnderfilled?30:14):(styleUnderfilled?26:12),minTurnover=style==='SCALP'?20_000_000:10_000_000,maxSpread=style==='SCALP'?8:18;
  const liquid=all.filter(x=>Number(x.lastPrice)>0&&Number(x.turnover24h||0)>=minTurnover&&(x.spreadBps==null||Number(x.spreadBps)<=maxSpread));
  const ranked=liquid.sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,rankedLimit);
  const rawAnalyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean),assessed=rawAnalyses.map(x=>{const strict=assessEntrySetup(x);const assessment=strict.verdict==='PASS'?strict:(x.coverageFallback?assessCoverageSetup(x):strict);return {...x,entryAssessment:assessment};}),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=rawAnalyses.map(toStandbyCandidate).filter(Boolean).filter(x=>!activeSymbols.has(canonical(x.symbol))).sort(compareSetupPriority).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);let promotion=null,afterCreate=await realtimePortfolioSnapshot(env);if(Number(afterCreate.styles?.[style]||0)<PORTFOLIO_POLICY.targetActivePerStyle)promotion=await promoteCryptoStandby(env,style,'SCAN_IMMEDIATE_REFILL');await kickCryptoServerMonitor(env).catch(()=>{});"""
new_scan="""const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style);
  const rankedLimit=style==='SCALP'?(styleUnderfilled?42:28):(styleUnderfilled?34:22);
  const liquid=all.filter(x=>stableUniverseEligible(x,style));
  const ranked=[...liquid].sort(stableUniverseCompare).slice(0,rankedLimit);
  const rawAnalyses=await analyzeCryptoBatch(ranked,style,6),assessed=rawAnalyses.map(x=>{const strict=assessEntrySetup(x);const assessment=strict.verdict==='PASS'?strict:(x.coverageFallback?assessCoverageSetup(x):strict);return {...x,entryAssessment:assessment};}),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=rawAnalyses.map(toStandbyCandidate).filter(Boolean).filter(x=>!activeSymbols.has(canonical(x.symbol))).sort(compareSetupPriority).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);let promotion=null,afterCreate=await realtimePortfolioSnapshot(env);if(Number(afterCreate.styles?.[style]||0)<styleTarget(style))promotion=await promoteCryptoStandby(env,style,'SCAN_IMMEDIATE_REFILL');await kickCryptoServerMonitor(env).catch(()=>{});"""
w=must_replace(w,old_scan,new_scan,'scan stable universe')
w=w.replace("note:'V3.15.2 fixed 2x2 reserve-pool engine: strict signals are preferred; every scan also derives hard-safety checked conditional pending reserves from the broader live analysis set, preserves prior valid reserves, and atomically promotes a reserve whenever a style drops below two.'","note:'V3.19 stable-universe 15-slot engine: target 10 SCALP + 5 SWING. Full live universe is refreshed every maintenance cycle; weak-liquidity/high-spread/fragile candidates are excluded before deep analysis; strict signals are preferred and fresh conditional LIMIT/STOP reserves refill depleted slots.'")

# Maintenance/status need asymmetric style targets.
w=must_replace(w,"const underfilled=Number(p.styles?.[style]||0)<PORTFOLIO_POLICY.minActivePerStyle;","const underfilled=Number(p.styles?.[style]||0)<styleTarget(style);",'maintenance underfilled')
w=must_replace(w,"if(Number(p.styles?.[style]||0)<PORTFOLIO_POLICY.targetActivePerStyle){","if(Number(p.styles?.[style]||0)<styleTarget(style)){",'maintenance promotion')
w=must_replace(w,"const portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env),missing=['SCALP','SWING'].filter(st=>Number(portfolio.styles?.[st]||0)<PORTFOLIO_POLICY.minActivePerStyle);","const portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env),missing=['SCALP','SWING'].filter(st=>Number(portfolio.styles?.[st]||0)<styleTarget(st));",'status missing')
w=w.replace("service:'SignalHub Crypto Fixed 2x2 + Watchlist gateway'","service:'SignalHub Crypto 10 SCALP + 5 SWING Stable Universe + Watchlist gateway'")
w=w.replace("scalp:'FIXED_2_ACTIVE_STRICT_THEN_CONDITIONAL_5M_15M_1H',swing:'FIXED_2_ACTIVE_STRICT_THEN_CONDITIONAL_1H_4H_1D'","scalp:'FIXED_10_ACTIVE_STABLE_LIQUID_UNIVERSE_5M_15M_1H',swing:'FIXED_5_ACTIVE_STABLE_LIQUID_UNIVERSE_1H_4H_1D'")

# Watchlist remains analysis-only; update its portfolio reference and keep weak coins visible as NO_TRADE rather than hiding them.
w=w.replace("activeBook:{targetScalp:2,targetSwing:2,note:'Watchlist does not consume or replace active slots.'}","activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist does not consume or replace the 15 active reference slots.'}")

# Discovery endpoint now surfaces the same stable universe the trading book uses.
old_discovery="const candidates=all.filter(t=>Number(t.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,limit).map(t=>({...t,marketRead:'DISCOVERY_FOR_BOT_JUDGMENT'}));"
new_discovery="const candidates=all.filter(t=>stableUniverseEligible(t,style)).sort(stableUniverseCompare).slice(0,limit).map(t=>({...t,marketRead:'STABLE_LIQUID_UNIVERSE_DISCOVERY'}));"
w=must_replace(w,old_discovery,new_discovery,'discovery filter')
w=w.replace("note:'No composite score is used. Candidates are handed to the market-judgment engine for regime classification and entry routing.'","note:'No composite score gate is used. Discovery first removes weak-liquidity / wide-spread / extreme-move symbols, then hands the stable live universe to the structure/liquidity engine.'")

# -----------------------------------------------------------------------------
# Android V3.19 — carries V3.18 Watchlist keyboard fix, updates target counts/UI copy.
# -----------------------------------------------------------------------------
a=must_replace(a,'private static final String APP_VERSION="3.18.0";','private static final String APP_VERSION="3.19.0";','app version')
a=a.replace('CRYPTO • 2 SCALP + 2 SWING','CRYPTO • 10 SCALP + 5 SWING')
a=a.replace('Bảng tham khảo luôn ưu tiên 2 SCALP + 2 SWING. Watchlist phân tích riêng coin bạn chọn.','Bảng tham khảo duy trì 10 SCALP + 5 SWING từ nhóm coin thanh khoản tốt. Watchlist phân tích riêng coin bạn chọn.')
a=a.replace('"mục tiêu 2 active",CYAN','"mục tiêu 10 active",CYAN')
a=a.replace('"mục tiêu 2 active",BLUE','"mục tiêu 5 active",BLUE')
a=a.replace('sectionHeader("4 tín hiệu tham khảo","Chạm vào từng coin để xem Entry / SL / TP và phân tích",MUTED)','sectionHeader("Tín hiệu gần nhất","Tổng mục tiêu 15 lệnh tham khảo • xem đầy đủ trong tab Tín hiệu",MUTED)')
a=a.replace('for(int i=0;i<Math.min(4,rows.size());i++)content.addView(homeSignalRow(rows.get(i)))','for(int i=0;i<Math.min(5,rows.size());i++)content.addView(homeSignalRow(rows.get(i)))')
a=a.replace('Không chiếm 4 slot tín hiệu chính','Không chiếm 15 slot tín hiệu chính')
a=a.replace('không chiếm 4 slot active','không chiếm 15 slot active')
a=a.replace('4 slot active','15 slot active')
a=a.replace('4 slot tín hiệu','15 slot tín hiệu')
a=a.replace('4 tín hiệu','15 tín hiệu')
a=a.replace('2 SCALP + 2 SWING','10 SCALP + 5 SWING')
# Keep the corrected V3.18 focus-safe Watchlist search behavior intact.
for required in ['private boolean watchSearchHasFocus()','private void showWatchKeyboard(','private List<String> watchMatches(','EditorInfo.IME_ACTION_SEARCH','!watchSearchHasFocus()']:
    if required not in a: raise SystemExit('V3.18 watch search regression: '+required)

g=must_replace(g,'versionCode 23','versionCode 24','version code')
g=must_replace(g,"versionName '3.18.0'","versionName '3.19.0'",'version name')

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.19 — 10 SCALP + 5 SWING stable-liquidity universe + V3.18 Watch search fix')
