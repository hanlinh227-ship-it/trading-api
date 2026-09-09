from pathlib import Path
W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text();a=A.read_text();g=G.read_text()

def rep(text,old,new,label):
    if old not in text: raise SystemExit('missing '+label)
    return text.replace(old,new)

# Patch release after V3.19 base patch was applied.
w=rep(w,"SIGNALHUB-V3-GATEWAY-3.19.0","SIGNALHUB-V3-GATEWAY-3.19.1",'worker version')
w=w.replace("versionCode: 24,\n  versionName: '3.19.0',","versionCode: 25,\n  versionName: '3.19.1',")
w=w.replace("title: 'SignalHub 3.19.0 10 Scalp + 5 Swing Stable Universe'","title: 'SignalHub 3.19.1 Stable Reference Coverage'")
w=w.replace("artifactName: 'SignalHub-Android-v3.19.0-10Scalp-5Swing-StableUniverse'","artifactName: 'SignalHub-Android-v3.19.1-10Scalp-5Swing-StableUniverse'")

# Prefer durable/high-turnover markets over merely tiny-spread markets.
old="function stableUniverseCompare(a,b){const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;const am=Math.abs(Number(a.change24hPct||0)),bm=Math.abs(Number(b.change24hPct||0));if(am!==bm)return am-bm;return Number(b.turnover24h||0)-Number(a.turnover24h||0);}"
new="function stableUniverseCompare(a,b){const at=Number(a.turnover24h||0),bt=Number(b.turnover24h||0);if(at!==bt)return bt-at;const ao=Number(a.openInterestValue||0),bo=Number(b.openInterestValue||0);if(ao!==bo)return bo-ao;const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;return Math.abs(Number(a.change24hPct||0))-Math.abs(Number(b.change24hPct||0));}"
w=rep(w,old,new,'stable ranking')

# A conditional-reference builder is used only when a liquid, cross-timeframe candidate has no immediate confirmed setup.
# It NEVER creates a fallback MARKET order: it waits for LIMIT/STOP confirmation and preserves structure-based SL/TP geometry.
needle='async function analyzeCryptoCandidate(t,style){'
if needle not in w: raise SystemExit('analyze needle missing')
helper=r'''function buildStableReferenceSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t?.lastPrice||0);if(!stableUniverseEligible(t,style)||!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,atr1=Number(a.atr),spread=Number(t.spreadBps??999),spreadPx=Math.max(0,px*spread/10000);
  let dir=0;const vote=2*Number(b.trend||0)+2*Number(c.trend||0)+Number(a.trend||0)+Number(a.momentum||0)+Number(b.momentum||0);
  if(style==='SWING'){if(b.trend!==0&&b.trend===c.trend&&a.trend!==-b.trend)dir=b.trend;else return null;}
  else{if(Math.abs(vote)>=2)dir=vote>0?1:-1;else return null;if(a.trend===-dir&&a.momentum===-dir)return null;}
  const entryBuffer=Math.max(atr1*(style==='SCALP'?.055:.10),spreadPx*3.0),pullback=dir>0?Math.max(a.ema20,a.recentLow+.30*atr1):Math.min(a.ema20,a.recentHigh-.30*atr1);
  let orderType,entry,entryModel;
  const pullbackCorrect=dir>0?pullback<px-entryBuffer*.20:pullback>px+entryBuffer*.20;
  if(pullbackCorrect&&Math.abs(px-pullback)<=atr1*(style==='SCALP'?1.25:1.80)){orderType='LIMIT';entry=pullback;entryModel='STABLE_UNIVERSE_PULLBACK_LIMIT';}
  else{orderType='STOP';entry=dir>0?Math.max(a.recentHigh,a.high)+entryBuffer:Math.min(a.recentLow,a.low)-entryBuffer;entryModel='STABLE_UNIVERSE_CONFIRMATION_STOP';}
  const stopBuffer=Math.max(atr1*(style==='SCALP'?.22:.34),spreadPx*(style==='SCALP'?3.2:3.8));
  const anchor=dir>0?Math.min(a.recentLow,a.low,a.ema50-.06*atr1):Math.max(a.recentHigh,a.high,a.ema50+.06*atr1);
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr1*(style==='SCALP'?.72:1.05),maxRisk=atr1*(style==='SCALP'?2.65:4.20);
  if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;if(dir>0){tp1=above([a.priorHigh,a.recentHigh],entry+risk*.95);tp2=above([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=above([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.20:2.85)));}else{tp1=below([a.priorLow,a.recentLow],entry-risk*.95);tp2=below([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=below([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.20:2.85)));}
  const cluster=cryptoRiskCluster(t.symbol),story=style==='SCALP'?'Stable-liquid 15m/1h context; wait for 5m pullback or confirmation trigger':'Stable-liquid H4/D1 context; wait for H1 pullback or confirmation trigger',regime=style==='SCALP'?'STABLE_LIQUID_REFERENCE_WAIT':'HTF_STABLE_LIQUID_REFERENCE_WAIT',rr=Math.abs(tp3-entry)/risk;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cluster,marketRegime:regime,marketStory:story,judgment:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • REFERENCE WAIT`,entryModel,coverageFallback:true,coverageTier:'STABLE_LIQUID_REFERENCE_PENDING',referenceFallback:true,slModel:'RECENT_STRUCTURE_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:'NORMAL',qualityEvidence:{contextAligned:true,liquidityEvent:false,displacementConfirmed:false,structureReclaimed:false,secondaryProviderConfirmed:false,entryNotChasing:true,invalidationStructural:true,targetPathClear:true,coverageConditional:true,stableUniverse:true},technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),change24hPct:Number(t.change24hPct||0),openInterestValue:t.openInterestValue==null?null:Number(t.openInterestValue),fundingRate:t.fundingRate==null?null:Number(t.fundingRate),sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,`liquidity floor passed: turnover ${Math.round(Number(t.turnover24h||0))} • spread ${spread.toFixed(2)} bps`,`SL beyond recent execution structure plus ATR/spread buffer`,`pending trigger only — no forced market entry`]},'CRYPTO',style);
}

'''
w=w.replace(needle,helper+needle,1)
w=rep(w,"const setup=buildCryptoSetup(t,style,stats);if(!setup)return null;","let setup=buildCryptoSetup(t,style,stats);if(!setup)setup=buildStableReferenceSetup(t,style,stats);if(!setup)return null;",'fallback invocation')
# If a secondary venue can be checked and directly opposes a reference fallback, discard it. No fabricated cross-provider confirmation.
w=rep(w,"if(!checked){setup.crossProviderConfirmation=false;setup.qualityEvidence.secondaryProviderConfirmed=false;setup.rationale.push('secondary provider unavailable: no new trade confirmation');}\n    return setup;","if(!checked){setup.crossProviderConfirmation=false;setup.qualityEvidence.secondaryProviderConfirmed=false;setup.rationale.push('secondary provider unavailable: no new trade confirmation');}\n    if(setup.referenceFallback&&checked&&!setup.crossProviderConfirmation)return null;\n    return setup;",'fallback secondary rule')

# The coverage assessment accepts this pending-only reference family because stable liquidity/context were already hard checked.
old="const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',pendingOnly:['LIMIT','STOP'].includes(order),structure:validSignalStructure(s),cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===(style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE'),liveSource:src>0,entryLocation,pendingReachable:triggerDistance<=(style==='SWING'?1.80:1.40),invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadHard:spread>=0&&spread<=rule.maxSpread,liquidityHard:turnover>=rule.minTurnover,dailyMoveHard:move<=rule.maxMove,openInterestHard:oi==null||!Number.isFinite(oi)||oi<=0||oi>=rule.minOi,fundingHard:funding==null||!Number.isFinite(funding)||funding<=rule.maxFunding};"
new="const reference=Boolean(s.referenceFallback),checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',pendingOnly:['LIMIT','STOP'].includes(order),structure:validSignalStructure(s),cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===(style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE'),liveSource:src>0,entryLocation,pendingReachable:triggerDistance<=(reference?(style==='SWING'?2.10:1.75):(style==='SWING'?1.80:1.40)),invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadHard:spread>=0&&spread<=rule.maxSpread,liquidityHard:turnover>=rule.minTurnover,dailyMoveHard:move<=rule.maxMove,openInterestHard:oi==null||!Number.isFinite(oi)||oi<=0||oi>=rule.minOi,fundingHard:funding==null||!Number.isFinite(funding)||funding<=rule.maxFunding};"
w=rep(w,old,new,'reference coverage reach')

# Expand deep analysis only while SCALP is under target; concurrency stays bounded.
w=w.replace("const rankedLimit=style==='SCALP'?(styleUnderfilled?42:28):(styleUnderfilled?34:22);","const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(64,liquid.length):32):(styleUnderfilled?40:24);")
# Previous replacement references liquid before declaration; reorder explicitly.
old="const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style);\n  const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(64,liquid.length):32):(styleUnderfilled?40:24);\n  const liquid=all.filter(x=>stableUniverseEligible(x,style));"
new="const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style);\n  const liquid=all.filter(x=>stableUniverseEligible(x,style));\n  const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(64,liquid.length):32):(styleUnderfilled?Math.min(44,liquid.length):24);"
w=rep(w,old,new,'ranked order')

# Android version only; all V3.18 keyboard fixes and V3.19 count wording remain.
a=rep(a,'private static final String APP_VERSION="3.19.0";','private static final String APP_VERSION="3.19.1";','app version')
g=rep(g,'versionCode 24','versionCode 25','version code')
g=rep(g,"versionName '3.19.0'","versionName '3.19.1'",'version name')

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched V3.19.1 stable reference pending fallback')
