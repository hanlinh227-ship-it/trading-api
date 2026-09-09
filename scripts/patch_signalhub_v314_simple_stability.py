from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
MAN=Path('signalhub-android/app/src/main/AndroidManifest.xml')
GRADLE=Path('signalhub-android/app/build.gradle')
RES=Path('signalhub-android/app/src/main/res/drawable')
CHECKPOINT=Path('SIGNALHUB_V3_CHECKPOINT_06_CRYPTO_STABILITY_UI.md')


def must_replace(text, old, new, label):
    if old not in text:
        raise SystemExit(f'{label}: pattern missing')
    return text.replace(old,new,1)

def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

# ---------------- Worker V3.14 ----------------
w=WORKER.read_text()
w=must_replace(w,"const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.13.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.14.0';",'worker version')
w=must_replace(w,"const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_05';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_06';",'checkpoint')
w=must_replace(w,"versionCode: 19,\n  versionName: '3.13.0',\n  title: 'SignalHub 3.13.0 Crypto Focus',","versionCode: 20,\n  versionName: '3.14.0',\n  title: 'SignalHub 3.14.0 Crypto Stability',",'release version')
w=must_replace(w,"artifactName: 'SignalHub-Android-v3.13.0-Crypto-Focus',","artifactName: 'SignalHub-Android-v3.14.0-Simple-Stable-Crypto',",'artifact name')
w=w.replace("  notes: [\n", "  notes: [\n    'V3.14 stability pass: SCALP no longer accepts a generic EMA trend pullback by itself; it needs a sweep/reclaim, displacement+reclaim, or confirmed breakout story.',\n    'V3.14 tightens secondary-exchange confirmation and live execution spread/liquidity conditions without reintroducing a numeric setup score.',\n    'V3.14 adds crypto risk-cluster concentration control so correlated meme-beta trades cannot occupy the whole active book.',\n    'V3.14 uses provider bid/ask for pending activation and live exit tracking, plus structure invalidation before a pending entry is allowed to fill.',\n    'V3.14 adds a stability endpoint separating infrastructure health from trading evidence/sample adequacy.',\n",1)

# Custom risk cluster utility. This is portfolio concentration control, not a setup score.
w=must_replace(w,"const canonical = s => String(s || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');",
"const canonical = s => String(s || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');\nconst cryptoRiskCluster = symbol => {\n  const base=canonical(symbol).replace(/USDT$/,'');\n  if(['DOGE','SHIB','PEPE','BONK','WIF','FLOKI','MEME','NEIRO','BRETT','TURBO','POPCAT','PNUT','FARTCOIN','MOG','BOME','MEW','TRUMP','PENGU'].includes(base))return 'MEME';\n  if(['BTC','ETH'].includes(base))return 'MAJOR';\n  if(['SOL','BNB','ADA','AVAX','SUI','APT','TON','NEAR','DOT','ATOM','SEI'].includes(base))return 'L1';\n  if(['LINK','UNI','AAVE','MKR','CRV','LDO','PENDLE','JUP','RAY','INJ'].includes(base))return 'DEFI';\n  return 'ALT';\n};",'risk cluster utility')

# Update policy objects in both status policy and execution policy constant.
oldp="portfolioPolicy:{maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true}"
newp="portfolioPolicy:{maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE_QUALITY_FIRST',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true}"
w=must_replace(w,oldp,newp,'policy embedded')
oldc="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true});"
newc="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,maxActivePerRiskCluster:2,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE_QUALITY_FIRST',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true});"
w=must_replace(w,oldc,newc,'portfolio constant')
w=w.replace("qualityMode:'CRYPTO_ONLY_STRICT_STRUCTURE_NO_SCORE'","qualityMode:'CRYPTO_STABILITY_STRUCTURE_NO_SCORE'",1)
w=w.replace("entryAssessment:'HARD_STRUCTURE_CHECKS_NO_NUMERIC_SCORE'","entryAssessment:'V314_CRYPTO_EVIDENCE_CHECKS_NO_NUMERIC_SCORE'",1)

# True crypto concentration control inside the atomic reservation transaction.
needle="      if(active.filter(x=>String(x.style||'').toUpperCase()===style).length>=policy.maxActivePerStyle)return reject('MAX_ACTIVE_STYLE');\n"
insert=needle+"      const cluster=cryptoRiskCluster(symbol),clusterCount=active.filter(x=>cryptoRiskCluster(x.symbol)===cluster).length;\n      if(cluster==='MEME'&&clusterCount>=policy.maxMemeActiveTotal)return reject('MAX_MEME_CLUSTER');\n      if(clusterCount>=policy.maxActivePerRiskCluster)return reject(`MAX_RISK_CLUSTER:${cluster}`);\n      s.riskCluster=cluster;\n"
w=must_replace(w,needle,insert,'atomic cluster control')

# Crypto execution lifecycle: use tradable bid/ask, not last price, and invalidate pending orders at structure anchor before SL.
w=must_replace(w,"      }else{const last=Number(q.lastPrice||q.last||q.mid||0);entryPx=last;exitPx=last;}",
"      }else{const last=Number(q.lastPrice||q.last||q.mid||0),bid=Number(q.bid||last||0),ask=Number(q.ask||last||0);entryPx=dir>0?ask:bid;exitPx=dir>0?bid:ask;}",'crypto bid ask execution')
w=must_replace(w,"        const invalidated=dir>0?exitPx<=sl:exitPx>=sl;",
"        const structureInvalidation=Number(s.invalidationLevel||sl),invalidated=dir>0?exitPx<=structureInvalidation:exitPx>=structureInvalidation;",'pending structure invalidation')
w=must_replace(w,"          s.status='OPEN';s.lifecycle='ACTIVE';s.entryState='LIVE';s.triggeredAt=at;s.triggerPrice=entryPx;s.actualEntry=s.actualEntry||entry;s.executionStatus='PRICE_TRIGGERED_AWAITING_BROKER_CONFIRM';eventType='TRIGGERED';mutated=true;",
"          s.status='OPEN';s.lifecycle='ACTIVE';s.entryState='LIVE';s.triggeredAt=at;s.triggerPrice=entryPx;s.actualEntry=entryPx;s.executionStatus='PROVIDER_BID_ASK_TRIGGERED';eventType='TRIGGERED';mutated=true;",'actual entry')
w=must_replace(w,"        if(hitTp||hitSl){s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=hitTp?tp:sl;s.resultR=hitTp?Number(s.targetRR||0):-1;s.resolution='REALTIME_EVENT_TRACKER';eventType=s.outcome;mutated=true;delete reg[id];dirty=true;}",
"        if(hitTp||hitSl){const ae=Number(s.actualEntry||entry),risk=Math.abs(ae-sl),exit=hitTp?tp:sl;s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=exit;s.resultR=risk>0?Number((dir*(exit-ae)/risk).toFixed(4)):(hitTp?Number(s.targetRR||0):-1);s.resolution='PROVIDER_BID_ASK_REALTIME_TRACKER';eventType=s.outcome;mutated=true;delete reg[id];dirty=true;}",'realistic result r')

# More explicit candle evidence: displacement and EMA reclaim.
w=must_replace(w,"  const impulse=Math.abs(last.c-last.o)/aa,extensionAtr=Math.abs(last.c-e20)/aa;\n  return {close:last.c,open:last.o,high:last.h,low:last.l,prevClose:prev?.c,ema20:e20,ema50:e50,rsi:rr,atr:aa,trend,slope,priorHigh,priorLow,recentHigh,recentLow,extensionAtr,momentum,sweepHigh,sweepLow,bosUp,bosDown,rangePosition,impulse,upperWickAtr:upperWick/aa,lowerWickAtr:lowerWick/aa};",
"  const impulse=Math.abs(last.c-last.o)/aa,extensionAtr=Math.abs(last.c-e20)/aa,bodyAtr=body/aa;\n  const bullDisplacement=last.c>last.o&&bodyAtr>=.30&&last.c>e20&&last.c>Number(prev?.h||e20),bearDisplacement=last.c<last.o&&bodyAtr>=.30&&last.c<e20&&last.c<Number(prev?.l||e20);\n  const emaReclaimUp=Number(prev?.c||last.c)<=e20&&last.c>e20&&last.c>last.o,emaReclaimDown=Number(prev?.c||last.c)>=e20&&last.c<e20&&last.c<last.o;\n  return {close:last.c,open:last.o,high:last.h,low:last.l,prevClose:prev?.c,ema20:e20,ema50:e50,rsi:rr,atr:aa,trend,slope,priorHigh,priorLow,recentHigh,recentLow,extensionAtr,momentum,sweepHigh,sweepLow,bosUp,bosDown,rangePosition,impulse,bodyAtr,bullDisplacement,bearDisplacement,emaReclaimUp,emaReclaimDown,upperWickAtr:upperWick/aa,lowerWickAtr:lowerWick/aa};",'tf evidence')

# Replace Crypto setup builder: no generic pullback alone; confirmation-first SCALP and HTF-confirmed SWING.
w=sub1(w,r"function buildCryptoSetup\(t,style,stats\)\{.*?\n\}\nasync function analyzeCryptoCandidate",r'''function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,spread=Number(t.spreadBps??0),atr1=a.atr;
  const breakoutUp=(a.bosUp||((a.priorHigh-px)/atr1>=-.05&&(a.priorHigh-px)/atr1<=.14))&&a.bullDisplacement&&a.momentum>=0;
  const breakoutDown=(a.bosDown||((px-a.priorLow)/atr1>=-.05&&(px-a.priorLow)/atr1<=.14))&&a.bearDisplacement&&a.momentum<=0;
  let dir=0,regime='NO_TRADE',story='',reclaimed=false,displacement=false,liquidityEvent=false;
  if(style==='SWING'){
    const htf=b.trend!==0&&b.trend===c.trend?b.trend:0;if(!htf)return null;
    if(htf===1&&a.sweepLow&&a.close>a.priorLow&&(a.bullDisplacement||a.close>a.ema20)){dir=1;regime='HTF_LIQUIDITY_SWEEP_RECLAIM';story='H4/D1 bullish + H1 sweep/reclaim with bullish recovery';reclaimed=true;liquidityEvent=true;displacement=a.bullDisplacement;}
    else if(htf===-1&&a.sweepHigh&&a.close<a.priorHigh&&(a.bearDisplacement||a.close<a.ema20)){dir=-1;regime='HTF_LIQUIDITY_SWEEP_RECLAIM';story='H4/D1 bearish + H1 sweep/reclaim with bearish recovery';reclaimed=true;liquidityEvent=true;displacement=a.bearDisplacement;}
    else if(htf===1&&(a.emaReclaimUp||a.bosUp)&&a.bullDisplacement&&a.momentum===1){dir=1;regime='HTF_TREND_RECLAIM';story='H4/D1 bullish + H1 displacement reclaims execution structure';reclaimed=true;displacement=true;}
    else if(htf===-1&&(a.emaReclaimDown||a.bosDown)&&a.bearDisplacement&&a.momentum===-1){dir=-1;regime='HTF_TREND_RECLAIM';story='H4/D1 bearish + H1 displacement reclaims execution structure';reclaimed=true;displacement=true;}
    else if(htf===1&&breakoutUp){dir=1;regime='HTF_BREAKOUT_CONFIRMATION';story='H4/D1 bullish + H1 displacement confirms breakout';reclaimed=a.bosUp;displacement=true;}
    else if(htf===-1&&breakoutDown){dir=-1;regime='HTF_BREAKOUT_CONFIRMATION';story='H4/D1 bearish + H1 displacement confirms breakdown';reclaimed=a.bosDown;displacement=true;}
    else return null;
  }else{
    const bullCtx=b.trend!==-1&&c.trend!==-1&&(b.trend===1||c.trend===1),bearCtx=b.trend!==1&&c.trend!==1&&(b.trend===-1||c.trend===-1),allBull=a.trend===1&&b.trend===1&&c.trend===1,allBear=a.trend===-1&&b.trend===-1&&c.trend===-1;
    if(a.sweepLow&&bullCtx&&a.close>a.priorLow&&(a.bullDisplacement||a.close>a.ema20)){dir=1;regime='LIQUIDITY_SWEEP_RECLAIM';story='5m downside sweep/reclaim + supportive 15m/1h context';reclaimed=true;liquidityEvent=true;displacement=a.bullDisplacement;}
    else if(a.sweepHigh&&bearCtx&&a.close<a.priorHigh&&(a.bearDisplacement||a.close<a.ema20)){dir=-1;regime='LIQUIDITY_SWEEP_RECLAIM';story='5m upside sweep/reclaim + supportive 15m/1h context';reclaimed=true;liquidityEvent=true;displacement=a.bearDisplacement;}
    else if(b.trend===1&&c.trend===1&&a.emaReclaimUp&&a.bullDisplacement&&a.momentum===1){dir=1;regime='TREND_RECLAIM_CONFIRMED';story='15m/1h bullish + 5m displacement reclaims EMA structure';reclaimed=true;displacement=true;}
    else if(b.trend===-1&&c.trend===-1&&a.emaReclaimDown&&a.bearDisplacement&&a.momentum===-1){dir=-1;regime='TREND_RECLAIM_CONFIRMED';story='15m/1h bearish + 5m displacement reclaims EMA structure';reclaimed=true;displacement=true;}
    else if(allBull&&a.bullDisplacement&&a.extensionAtr<=.24){dir=1;regime='TREND_CONTINUATION_CONFIRMED';story='5m/15m/1h bullish alignment + fresh 5m displacement';displacement=true;reclaimed=a.bosUp||a.close>a.recentHigh;}
    else if(allBear&&a.bearDisplacement&&a.extensionAtr<=.24){dir=-1;regime='TREND_CONTINUATION_CONFIRMED';story='5m/15m/1h bearish alignment + fresh 5m displacement';displacement=true;reclaimed=a.bosDown||a.close<a.recentLow;}
    else if(breakoutUp&&b.trend===1&&c.trend!==-1){dir=1;regime='BREAKOUT_CONFIRMATION';story='5m displacement at breakout edge + bullish 15m context';reclaimed=a.bosUp;displacement=true;}
    else if(breakoutDown&&b.trend===-1&&c.trend!==1){dir=-1;regime='BREAKOUT_CONFIRMATION';story='5m displacement at breakdown edge + bearish 15m context';reclaimed=a.bosDown;displacement=true;}
    else return null;
  }

  const spreadPx=Math.max(0,px*spread/10000),entryBuffer=Math.max(atr1*(style==='SCALP'?.045:.08),spreadPx*(style==='SCALP'?2.5:3.0));
  const tooExtended=Math.abs(a.extensionAtr)>(style==='SCALP'?.28:.24),badMarketLocation=dir>0?a.rangePosition>.78:a.rangePosition<.22;
  let orderType='MARKET',entry=px,entryModel=liquidityEvent?'SWEEP_RECLAIM_MARKET':'CONFIRMED_STRUCTURE_MARKET';
  if(regime.includes('BREAKOUT')){orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='CONFIRMED_BREAKOUT_TRIGGER';}
  else if(!liquidityEvent&&(tooExtended||badMarketLocation||regime.includes('RECLAIM'))){
    const raw=dir>0?Math.max(a.ema20,a.recentLow+.42*atr1):Math.min(a.ema20,a.recentHigh-.42*atr1);
    if((dir>0&&raw<px-entryBuffer*.35)||(dir<0&&raw>px+entryBuffer*.35)){orderType='LIMIT';entry=raw;entryModel='RETEST_AFTER_DISPLACEMENT_RECLAIM';}
    else if(tooExtended||style==='SWING')return null;
  }

  const stopBuffer=Math.max(atr1*(style==='SCALP'?.22:.34),spreadPx*(style==='SCALP'?3.0:3.5));
  let anchor;
  if(dir>0){anchor=Math.min(a.low,a.recentLow,a.ema50-.08*atr1);if(liquidityEvent)anchor=Math.min(anchor,a.priorLow);if(style==='SWING')anchor=Math.min(anchor,a.priorLow,b.low,b.recentLow,b.ema50-.10*b.atr);}
  else{anchor=Math.max(a.high,a.recentHigh,a.ema50+.08*atr1);if(liquidityEvent)anchor=Math.max(anchor,a.priorHigh);if(style==='SWING')anchor=Math.max(anchor,a.priorHigh,b.high,b.recentHigh,b.ema50+.10*b.atr);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr1*(style==='SCALP'?.75:1.12),maxRisk=atr1*(style==='SCALP'?2.10:4.0);
  if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;
  if(dir>0){tp1=above([a.priorHigh,a.recentHigh],entry+risk*.95);tp2=above([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=above([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.20:2.85)));}
  else{tp1=below([a.priorLow,a.recentLow],entry-risk*.95);tp2=below([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=below([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.20:2.85)));}
  const rr=Math.abs(tp3-entry)/risk,spreadState=spread>(style==='SCALP'?8:18)?'WIDE':'NORMAL',cluster=cryptoRiskCluster(t.symbol);
  const qualityEvidence={contextAligned:true,liquidityEvent,displacementConfirmed:displacement,structureReclaimed:reclaimed,secondaryProviderConfirmed:false,entryNotChasing:orderType!=='MARKET'||!tooExtended,invalidationStructural:Number.isFinite(anchor),targetPathClear:dir>0?sl<entry&&entry<tp1&&tp1<tp2&&tp2<tp3:sl>entry&&entry>tp1&&tp1>tp2&&tp2>tp3};
  const judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • EVIDENCE CONFIRMED`;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cluster,marketRegime:regime,marketStory:story,judgment,entryModel,slModel:'STRUCTURE_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:spreadState,qualityEvidence,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,bullDisplacement:a.bullDisplacement,bearDisplacement:a.bearDisplacement,emaReclaimUp:a.emaReclaimUp,emaReclaimDown:a.emaReclaimDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,`SL outside structural invalidation ${Number(anchor.toPrecision(8))} plus volatility/spread buffer`,`TP ladder targets local/context/HTF liquidity before expansion`,`risk cluster ${cluster} • RSI ${a.rsi.toFixed(1)} • extension ${a.extensionAtr.toFixed(2)} ATR • spread ${spread.toFixed(2)} bps`]},'CRYPTO',style);
}
async function analyzeCryptoCandidate''','crypto setup builder')

# Stronger secondary provider confirmation; neutral is no longer silently treated as confirmation.
w=sub1(w,r"async function analyzeCryptoCandidate\(t,style\)\{.*?\n\}\n\nfunction v31Prefix",r'''async function analyzeCryptoCandidate(t,style){
  try{
    const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;
    const setup=buildCryptoSetup(t,style,stats);if(!setup)return null;
    const dir=String(setup.side||'').toUpperCase()==='LONG'?1:-1,contextInterval=intervalMap[style][1],primary=String(t.exchange||'').toUpperCase();
    const probes=[['BYBIT',bybitCandles],['OKX',okxCandles],['BINANCE',binanceCandles]].filter(x=>x[0]!==primary);let checked=false;
    for(const [provider,fn] of probes){
      try{
        const sec=tfStats(await fn(t.symbol,contextInterval));if(!sec)continue;checked=true;
        const opposing=sec.trend===-dir||sec.momentum===-dir,supporting=sec.trend===dir||sec.momentum===dir;
        const confirmed=style==='SWING'?(sec.trend===dir&&!opposing):(!opposing&&supporting);
        setup.technicalAtIssue.crossProvider=provider;setup.technicalAtIssue.crossTrend=sec.trend;setup.technicalAtIssue.crossMomentum=sec.momentum;setup.crossProviderConfirmation=confirmed;
        setup.qualityEvidence.secondaryProviderConfirmed=confirmed;setup.rationale.push(`secondary ${provider} ${contextInterval} ${confirmed?'confirms direction':'does not confirm direction'}`);break;
      }catch{}
    }
    if(!checked){setup.crossProviderConfirmation=false;setup.qualityEvidence.secondaryProviderConfirmed=false;setup.rationale.push('secondary provider unavailable: no new trade confirmation');}
    return setup;
  }catch{return null;}
}

function v31Prefix''','secondary confirmation')

# Evidence-based hard checks: no score, no time gate, no generic trend entry.
w=sub1(w,r"function assessEntrySetup\(raw\)\{.*?\n\}\nfunction setupPriority",r'''function assessEntrySetup(raw){
  const s=raw||{},dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{};
  const style=String(s.style||'SCALP').toUpperCase(),order=String(s.orderType||'').toUpperCase(),regime=String(s.marketRegime||''),expectedStyle=style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE',trends=Array.isArray(tech.tfTrend)?tech.tfTrend.map(signOf):[];
  const targetPath=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3,contextAligned=style==='SWING'?trends.length>=3&&trends[1]===dir&&trends[2]===dir:trends.length>=3&&trends[1]!==-dir&&trends[2]!==-dir&&(trends[1]===dir||trends[2]===dir);
  const ext=Math.abs(Number(tech.extensionAtr||0)),risk=Math.abs(entry-sl),triggerDistance=risk>0&&src>0?Math.abs(src-entry)/risk:999,maxMarketExt=style==='SWING'?.16:.22;
  const marketLocation=order==='MARKET'?(regime.includes('LIQUIDITY')||ext<=maxMarketExt):order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false,pendingReachable=order==='MARKET'||triggerDistance<=(order==='LIMIT'?(style==='SWING'?.90:.75):(style==='SWING'?.50:.45));
  const spread=Number(tech.spreadBps||0),turnover=Number(tech.turnover24h||0),rsi=Number(tech.rsi||50),spreadQuality=spread>=0&&spread<=(style==='SWING'?16:7),liquidityQuality=turnover>=(style==='SWING'?10_000_000:20_000_000),momentumSanity=dir>0?rsi<=70:rsi>=30;
  const confirmationStory=regime.includes('SWEEP')||regime.includes('RECLAIM')||regime.includes('CONFIRMATION'),displacementOrLiquidity=Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),structureEvidence=Boolean(ev.structureReclaimed)||Boolean(ev.liquidityEvent)||regime.includes('BREAKOUT');
  const checks={cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',cleanStory:typeof s.marketStory==='string'&&s.marketStory.length>=18,styleModel:s.styleExecutionModel===expectedStyle,contextAligned,confirmationStory,displacementOrLiquidity,structureEvidence,secondaryProvider:s.crossProviderConfirmation===true,entryLocation:src>0&&marketLocation,pendingReachable,invalidation:Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),targetPath,spreadQuality,liquidityQuality,momentumSanity,executionConditions:String(s.executionCaution||'NORMAL').toUpperCase()!=='WIDE',liveSource:src>0};
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;s.qualityEvidence={...ev,contextAligned,secondaryProviderConfirmed:s.crossProviderConfirmation===true,entryNotChasing:src>0&&marketLocation,invalidationStructural:checks.invalidation,targetPathClear:targetPath};
  return {verdict:pass?'PASS':'NO_TRADE',method:'V314_CRYPTO_EVIDENCE_CHECKS_NO_NUMERIC_SCORE',checks,failed,executionFacts:{extensionAtr:Number(ext.toFixed(3)),triggerDistanceR:Number(triggerDistance.toFixed(3)),spreadBps:spread,turnover24h:turnover,riskCluster:s.riskCluster||cryptoRiskCluster(s.symbol)}};
}
function setupPriority''','entry assessment')

# Prefer confirmation families and deeper liquidity; no setup score.
w=sub1(w,r"function setupPriority\(s\)\{.*?\n\}\nfunction compareSetupPriority",r'''function setupPriority(s){
  const r=String(s.marketRegime||''),family=r.includes('LIQUIDITY')?0:r.includes('RECLAIM')?1:r.includes('BREAKOUT')?2:r.includes('CONTINUATION')?3:4,spread=Number(s?.technicalAtIssue?.spreadBps||999),ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),turnover=Number(s?.technicalAtIssue?.turnover24h||0);
  return [family,spread,ext,-turnover];
}
function compareSetupPriority''','priority')

# Updated V3.14 lifecycle labels and crypto scan execution thresholds.
w=w.replace('REPLACED_BY_V313_CRYPTO_ONLY_QUALITY','REPLACED_BY_V314_STABILITY_ENGINE')
w=w.replace('V313_CRYPTO_ONLY_RESET','V314_STABILITY_RESET')
w=w.replace('`V312-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`','`V314-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`')
w=must_replace(w,"  const rankedLimit=style==='SCALP'?(styleEmpty?22:16):(styleEmpty?18:14),minTurnover=style==='SCALP'?8_000_000:5_000_000,maxSpread=style==='SCALP'?12:24;",
"  const rankedLimit=style==='SCALP'?(styleEmpty?20:14):(styleEmpty?18:12),minTurnover=style==='SCALP'?20_000_000:10_000_000,maxSpread=style==='SCALP'?8:18;",'scan liquidity')
w=w.replace("note:'Crypto-only quality engine. SCALP and SWING use separate hard structure rules; no predicted win-rate or numeric score is fabricated.'","note:'V3.14 crypto stability engine: confirmation-first SCALP/SWING, secondary-provider evidence and cluster concentration control. No predicted win-rate or numeric setup score.'")

# Add stability endpoint that explicitly separates system reliability from trading evidence.
stability=r'''
async function v314Stability(env){
  const portfolio=await realtimePortfolioSnapshot(env),monitor=await cryptoServerMonitorStatus(env),styles={};let totalResolved=0,totalTp=0,totalSl=0,totalNetR=0;
  for(const style of ['SCALP','SWING']){
    const rows=await getV31Signals(env,'CRYPTO',style),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
    styles[style]={resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,evidenceState:resolved.length>=30?'MATURE_SAMPLE':resolved.length>=10?'BUILDING_SAMPLE':'INSUFFICIENT_SAMPLE'};totalResolved+=resolved.length;totalTp+=tp;totalSl+=sl;totalNetR+=netR;
  }
  const monitorHealthy=monitor?.ok!==false&&monitor?.running!==false&&Array.isArray(monitor?.errors)&&monitor.errors.length===0,infrastructureState=monitorHealthy?'STABLE':'DEGRADED',warnings=[];
  if(styles.SCALP.resolved>0&&styles.SCALP.netRResolved<0)warnings.push('SCALP_RESOLVED_NET_R_NEGATIVE');if(styles.SCALP.resolved<30)warnings.push('SCALP_SAMPLE_SMALL');if(styles.SWING.resolved<30)warnings.push('SWING_SAMPLE_SMALL');if(!monitorHealthy)warnings.push('CRYPTO_MONITOR_DEGRADED');
  return json({ok:true,version:V3_VERSION,checkpoint:CHECKPOINT,mode:'CRYPTO_ONLY_STABILITY',infrastructure:{state:infrastructureState,monitor,portfolio},tradingEvidence:{state:totalResolved>=60?'MATURE':'NOT_YET_PROVEN',resolved:totalResolved,tp:totalTp,sl:totalSl,winRateResolved:totalResolved?totalTp/totalResolved*100:null,netRResolved:Number(totalNetR.toFixed(2)),styles},warnings,note:'Infrastructure stability and trading performance are separate. Win rate is descriptive only from closed TP/SL trades; it is not a predicted probability.'});
}
'''
w=must_replace(w,"async function v3Status(env,ctx){",stability+"\nasync function v3Status(env,ctx){",'stability endpoint function')
w=must_replace(w,"    if(url.pathname==='/v3/status'&&req.method==='GET')return v3Status(env,ctx);",
"    if(url.pathname==='/v3/status'&&req.method==='GET')return v3Status(env,ctx);\n    if(url.pathname==='/v3/stability'&&req.method==='GET')return v314Stability(env);",'stability route')
w=w.replace("mode:'CRYPTO_ONLY_QUALITY'","mode:'CRYPTO_ONLY_STABILITY'")
w=w.replace("service:'SignalHub Crypto SCALP/SWING gateway'","service:'SignalHub Crypto Stability SCALP/SWING gateway'")
w=w.replace("scalp:'STRICT_5M_15M_1H'","scalp:'CONFIRMATION_FIRST_5M_15M_1H'")
w=w.replace("swing:'STRICT_1H_4H_1D'","swing:'HTF_CONFIRMED_1H_4H_1D'")
WORKER.write_text(w)

# ---------------- Android V3.14 simple UI ----------------
a=ACT.read_text()
a=must_replace(a,'import android.widget.Button;','import android.widget.Button;\nimport android.widget.ImageView;','ImageView import')
a=must_replace(a,'private static final String APP_VERSION="3.13.0";','private static final String APP_VERSION="3.14.0";','app version')
a=a.replace('private static final long PAGE_REFRESH_MS=3000L;','private static final long PAGE_REFRESH_MS=2500L;')
a=a.replace('Typeface.create(Typeface.MONOSPACE,bold?Typeface.BOLD:Typeface.NORMAL)','Typeface.create(Typeface.DEFAULT,bold?Typeface.BOLD:Typeface.NORMAL)')
a=a.replace('b.setTypeface(Typeface.MONOSPACE,Typeface.BOLD);','b.setTypeface(Typeface.DEFAULT,Typeface.BOLD);')
a=a.replace('Typeface.create(Typeface.MONOSPACE,Typeface.BOLD)','Typeface.DEFAULT_BOLD')

# Clean header with local vector logo and only relevant crypto status.
a=sub1(a,r"    private void buildUi\(\)\{.*?\n    \}\n\n    private void setStyle",r'''    private void buildUi(){
        LinearLayout root=column();root.setBackgroundColor(BG);
        LinearLayout head=column();head.setPadding(dp(16),dp(12),dp(16),dp(8));
        LinearLayout top=row();ImageView brand=new ImageView(this);brand.setImageResource(R.drawable.ic_signalhub);brand.setColorFilter(CYAN);LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(dp(34),dp(34));bp.setMargins(0,0,dp(10),0);top.addView(brand,bp);
        LinearLayout titles=column();TextView logo=tv("SignalHub",22,TEXT,true);subtitle=tv("CRYPTO • SCALP / SWING • V3.14",9,MUTED,false);titles.addView(logo);titles.addView(subtitle);top.addView(titles,new LinearLayout.LayoutParams(0,-2,1f));cryptoLive=chip("CRYPTO • OFFLINE",RED);top.addView(cryptoLive);head.addView(top);
        signalControls=column();LinearLayout styles=row();scalpBtn=button("SCALP",true,v->setStyle("SCALP"));swingBtn=button("SWING",false,v->setStyle("SWING"));LinearLayout.LayoutParams s1=new LinearLayout.LayoutParams(0,dp(42),1f);s1.setMargins(0,dp(10),dp(4),0);LinearLayout.LayoutParams s2=new LinearLayout.LayoutParams(0,dp(42),1f);s2.setMargins(dp(4),dp(10),0,0);styles.addView(scalpBtn,s1);styles.addView(swingBtn,s2);signalControls.addView(styles);head.addView(signalControls);root.addView(head);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);content=column();content.setPadding(dp(16),dp(4),dp(16),dp(14));scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1f));bottom=row();bottom.setPadding(dp(8),dp(5),dp(8),dp(7));bottom.setBackgroundColor(PANEL);root.addView(bottom);setContentView(root);drawBottom();signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);
    }

    private void setStyle''','build UI')

# Four-tab navigation only: alerts are delivered as Android notifications, not a full screen.
a=sub1(a,r"    private void drawBottom\(\)\{.*?\n    \}\n    private void swap",r'''    private void drawBottom(){
        bottom.removeAllViews();String[] keys={"HOME","SIGNALS","STATS","SETTINGS"},names={"TRANG CHỦ","TÍN HIỆU","THỐNG KÊ","CÀI ĐẶT"};int[] icons={R.drawable.ic_home,R.drawable.ic_signal,R.drawable.ic_stats,R.drawable.ic_settings};
        for(int i=0;i<keys.length;i++){final String x=keys[i];Button b=button(names[i],screen.equals(x),v->selectScreen(x));b.setTextSize(9);b.setGravity(Gravity.CENTER);b.setCompoundDrawablesWithIntrinsicBounds(0,icons[i],0,0);b.setCompoundDrawablePadding(dp(2));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(58),1f);p.setMargins(dp(2),0,dp(2),0);bottom.addView(b,p);}
    }
    private void swap''','bottom nav')
a=must_replace(a,'        else if(screen.equals("ALERTS"))renderAlerts(animate);\n        else renderSettings(animate);','        else renderSettings(animate);','render current')

# Crypto-only list helper.
a=sub1(a,r"    private List<JSONObject> allSignals\(\)\{.*?\n    \}",r'''    private List<JSONObject> allSignals(){
        List<JSONObject> out=new ArrayList<>();for(String st:new String[]{"SCALP","SWING"}){JSONArray arr=signalCache.get("CRYPTO:"+st);if(arr==null)continue;for(int i=0;i<arr.length();i++){JSONObject s=arr.optJSONObject(i);if(s!=null)out.add(s);}}out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }''','all signals')

# Single style performance summary.
a=sub1(a,r"    private String performanceSummary\(\)\{.*?\n    \}",r'''    private String performanceSummary(){JSONObject p=perfCache.get("CRYPTO:"+style);if(p==null)return "Hiệu suất: chưa đủ dữ liệu";int n=p.optInt("resolved",0);return n==0?"Hiệu suất: chưa có lệnh đóng":("WR "+p.optString("winRateLabel","—")+"  •  Net "+String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)));}''','performance summary')

# Simpler signal card: visual coin badge, current price, Entry/SL/TP3, one progress gauge.
a=sub1(a,r"    private View signalCard\(JSONObject s\)\{.*?\n    \}\n\n    private TextView metric",r'''    private View signalCard(JSONObject s){
        LinearLayout c=card();String sym=s.optString("symbol","—"),side=sideVi(s.optString("side","—")),signalStyle=s.optString("style",style),id=s.optString("signalId",s.optString("id",sym+":"+signalStyle));int col=side.equals("BUY")?GREEN:RED;double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp3=s.optDouble("tp3",s.optDouble("tp",0)),px=priceFor(s,e);
        LinearLayout h=row();ImageView coin=new ImageView(this);coin.setImageResource(R.drawable.ic_crypto_coin);coin.setColorFilter(CYAN);LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(dp(30),dp(30));cp.setMargins(0,0,dp(9),0);h.addView(coin,cp);LinearLayout names=column();names.addView(tv(sym,17,TEXT,true));names.addView(tv(signalStyle+" • "+s.optString("executionPriceAuthority",s.optString("provider","CRYPTO")),9,MUTED,false));h.addView(names,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));LinearLayout.LayoutParams op=new LinearLayout.LayoutParams(-2,-2);op.setMargins(dp(6),0,0,0);TextView oc=chip(orderDisplay(s,px),orderColor(s,px));h.addView(oc,op);c.addView(h);
        TextView pv=tv(fmt(px),23,TEXT,true);pv.setPadding(0,dp(9),0,0);c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,"CRYPTO");TextView pnl=tv(tradeStatusText(s,px),11,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(5),0,dp(1));c.addView(pnl);pnlViews.put(id,pnl);
        if(isDisplayLive(s,px)){TradeGauge g=new TradeGauge();g.setData(currentR(s,px),targetR(s));c.addView(g,new LinearLayout.LayoutParams(-1,dp(58)));gaugeViews.put(id,g);}else{EntryGauge g=new EntryGauge();g.setData(s,px);c.addView(g,new LinearLayout.LayoutParams(-1,dp(62)));entryGaugeViews.put(id,g);}
        LinearLayout lv=row();lv.addView(simpleLevel("ENTRY",fmt(e),TEXT),new LinearLayout.LayoutParams(0,-2,1f));lv.addView(simpleLevel("SL",fmt(sl),RED),new LinearLayout.LayoutParams(0,-2,1f));lv.addView(simpleLevel("TP3",fmt(tp3),GREEN),new LinearLayout.LayoutParams(0,-2,1f));c.addView(lv);
        TextView reason=tv(shortReason(s),9,MUTED,false);reason.setPadding(0,dp(7),0,0);c.addView(reason);pressFeedback(c);c.setClickable(true);c.setOnClickListener(v->{selectedSignal=s;detail=true;renderDetail(s,true);});return c;
    }
    private View simpleLevel(String k,String v,int color){LinearLayout x=column();x.setPadding(dp(2),dp(7),dp(2),0);x.addView(tv(k,8,MUTED,true));x.addView(tv(v,11,color,true));return x;}
    private String shortReason(JSONObject s){String r=s.optString("marketRegime","MARKET READ").replace('_',' '),cluster=s.optString("riskCluster","");return cluster.isEmpty()?r:(r+" • "+cluster);}

    private TextView metric''','signal card')

# Signals screen: LIVE + WAITING, no three-section clutter.
a=sub1(a,r"    private void renderSignals\(boolean animate\)\{.*?\n    \}\n\n    private void addCryptoSignalGroup",r'''    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText("CRYPTO REALTIME • "+style);
            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),waitRows=new ArrayList<>();for(JSONObject x:rows){double px=priceFor(x,x.optDouble("entry",0));if(isDisplayLive(x,px))liveRows.add(x);else waitRows.add(x);}
            LinearLayout top=row();top.addView(tv(style+" SIGNALS",18,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));top.addView(chip(cryptoState,stateColor(cryptoState)));content.addView(top);LinearLayout summary=card();summary.addView(tv(liveRows.size()+" LIVE   •   "+waitRows.size()+" CHỜ ENTRY",14,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,false));content.addView(summary);addCryptoSignalGroup("LIVE",liveRows,GREEN);addCryptoSignalGroup("CHỜ ENTRY",waitRows,YELLOW);
        };if(animate)swap(body);else body.run();updateAllPriceViews();
    }

    private void addCryptoSignalGroup''','signals screen')
a=a.replace('LinearLayout z=card();z.addView(tv("Chưa có setup đạt hard-quality trong nhóm này.",10,MUTED,true));','LinearLayout z=card();z.addView(tv("Chưa có setup phù hợp lúc này.",10,MUTED,true));')

# Home: one glance, no dense dashboard.
a=sub1(a,r"    private void renderHome\(boolean animate\)\{.*?\n    \};if\(animate\)swap\(body\);else body\.run\(\);updateAllPriceViews\(\);\}",r'''    private void renderHome(boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText("CRYPTO SIGNALS • SIMPLE & REALTIME");
        LinearLayout hero=card();LinearLayout h=row();LinearLayout left=column();left.addView(tv("CRYPTO SIGNALS",11,CYAN,true));left.addView(tv(systemState.equals("RUNNING")?"Hệ thống đang hoạt động":"Đang kết nối lại",21,TEXT,true));left.addView(tv(cryptoProvider+" • "+cryptoState,9,stateColor(cryptoState),true));h.addView(left,new LinearLayout.LayoutParams(0,-2,1f));ImageView mark=new ImageView(this);mark.setImageResource(R.drawable.ic_signalhub);mark.setColorFilter(CYAN);h.addView(mark,new LinearLayout.LayoutParams(dp(44),dp(44)));hero.addView(h);content.addView(hero);
        LinearLayout counts=row();View sc=statTile("S","SCALP",String.valueOf(countStyle("SCALP")),"active + waiting",CYAN),sw=statTile("W","SWING",String.valueOf(countStyle("SWING")),"active + waiting",BLUE);LinearLayout.LayoutParams p1=new LinearLayout.LayoutParams(0,-2,1f);p1.setMargins(0,0,dp(4),0);LinearLayout.LayoutParams p2=new LinearLayout.LayoutParams(0,-2,1f);p2.setMargins(dp(4),0,0,0);counts.addView(sc,p1);counts.addView(sw,p2);content.addView(counts);
        JSONObject ps=perfCache.get("CRYPTO:SCALP"),pw=perfCache.get("CRYPTO:SWING");LinearLayout evidence=card();evidence.addView(tv("HIỆU SUẤT THỰC TẾ",11,TEXT,true));evidence.addView(evidenceLine("SCALP",ps));evidence.addView(evidenceLine("SWING",pw));evidence.addView(tv("Chỉ tính TP/SL đã đóng • sample nhỏ sẽ được ghi rõ.",8,MUTED,false));content.addView(evidence);
        List<JSONObject> rows=allSignals();content.addView(tv("LỆNH GẦN NHẤT",12,TEXT,true));if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Bot đang chờ cấu trúc phù hợp.",10,MUTED,false));content.addView(z);}else content.addView(signalCard(rows.get(0)));
    };if(animate)swap(body);else body.run();updateAllPriceViews();}
    private int countStyle(String st){int n=0;for(JSONObject s:allSignals())if(st.equals(s.optString("style","")))n++;return n;}
    private View evidenceLine(String st,JSONObject p){LinearLayout r=row();r.setPadding(0,dp(5),0,dp(5));r.addView(tv(st,10,st.equals("SCALP")?CYAN:BLUE,true),new LinearLayout.LayoutParams(0,-2,1f));if(p==null){r.addView(tv("đang tải",9,MUTED,false));return r;}int n=p.optInt("resolved",0);String x=n==0?"chưa có mẫu":p.optString("winRateLabel","—")+" • "+String.format(Locale.US,"%+.1fR",p.optDouble("netRResolved",0));r.addView(tv(x,10,n>=30?TEXT:YELLOW,true));return r;}''','home')

# Stats wording: never imply a tiny sample is stable.
a=a.replace('subtitle.setText("PERFORMANCE STATISTICS • RESOLVED TRADES ONLY")','subtitle.setText("HIỆU SUẤT • CHỈ LỆNH ĐÃ ĐÓNG")')
a=a.replace('content.addView(tv("THỐNG KÊ HIỆU SUẤT",16,TEXT,true));','content.addView(tv("THỐNG KÊ",18,TEXT,true));')
a=a.replace('note.addView(tv("Win Rate chỉ tính lệnh đã đóng bằng TP/SL.",11,YELLOW,true));note.addView(tv("WATCH/PENDING không được tính thắng thua. Bot không dùng điểm số để quyết định entry.",9,MUTED,false));','note.addView(tv("WR chỉ là kết quả lệnh đã đóng, không phải xác suất thắng dự đoán.",10,YELLOW,true));note.addView(tv("Dưới 30 lệnh mỗi style: coi là dữ liệu sơ bộ.",9,MUTED,false));')

# Settings reduced to essentials.
a=sub1(a,r"    private void renderSettings\(boolean animate\)\{.*?\n    \};if\(animate\)swap\(body\);else body\.run\(\);\}",r'''    private void renderSettings(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CÀI ĐẶT • CRYPTO ONLY");content.addView(tv("CÀI ĐẶT",18,TEXT,true));
        LinearLayout notify=card();notify.addView(tv("THÔNG BÁO",12,TEXT,true));notify.addView(statusRow("Theo dõi nền",monitorStarted?"RUNNING":"OFFLINE"));notify.addView(statusRow("Quyền thông báo",notifyPermission()?"ONLINE":"OFFLINE"));if(!monitorStarted){Button b=button("BẬT THEO DÕI",true,v->ensureMonitor(true));notify.addView(b,new LinearLayout.LayoutParams(-1,dp(42)));}content.addView(notify);
        LinearLayout data=card();data.addView(tv("DỮ LIỆU",12,TEXT,true));data.addView(statusRow(cryptoProvider,cryptoState));data.addView(line("Execution","Theo đúng provider của từng signal",CYAN));data.addView(line("Pending","Server monitor ~1s",GREEN));content.addView(data);
        LinearLayout engine=card();engine.addView(tv("ENGINE",12,TEXT,true));engine.addView(line("SCALP","5m • 15m • 1h confirmation-first",CYAN));engine.addView(line("SWING","1h • 4h • 1D HTF-confirmed",BLUE));engine.addView(line("Risk cluster","Không dồn toàn bộ vào meme-beta",YELLOW));engine.addView(line("Version",APP_VERSION,TEXT));if(systemStatus!=null)engine.addView(line("Backend",systemStatus.optString("version","—"),MUTED));content.addView(engine);
    };if(animate)swap(body);else body.run();}''','settings')

# App now displays server lifecycle only; local pending touch is never promoted to LIVE.
a=a.replace('String market=s.optString("market","FOREX").toUpperCase(Locale.US)','String market=s.optString("market","CRYPTO").toUpperCase(Locale.US)')
a=a.replace('private String historicalWr(String market,String st){JSONObject p=perfCache.get(market+":"+st);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}', 'private String historicalWr(String market,String st){JSONObject p=perfCache.get("CRYPTO:"+st);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}')
ACT.write_text(a)

# Monitor branding update.
m=MON.read_text().replace('SignalHub V3.13 • CRYPTO QUALITY LIVE','SignalHub V3.14 • CRYPTO STABILITY LIVE')
MON.write_text(m)

# Manifest gets an actual local vector application icon.
man=MAN.read_text()
man=must_replace(man,'android:label="SignalHub"\n        android:usesCleartextTraffic','android:label="SignalHub"\n        android:icon="@drawable/ic_signalhub"\n        android:usesCleartextTraffic','manifest icon')
MAN.write_text(man)

# Gradle version.
g=GRADLE.read_text().replace('versionCode 19','versionCode 20').replace("versionName '3.13.0'","versionName '3.14.0'")
GRADLE.write_text(g)

# Lightweight vector asset system: no remote images at runtime and no tracking dependency.
RES.mkdir(parents=True,exist_ok=True)
assets={
'ic_signalhub.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FF28D9F5" android:pathData="M3,19L7,19L7,13L3,13ZM10,19L14,19L14,9L10,9ZM17,19L21,19L21,4L17,4Z"/></vector>''',
'ic_home.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="22dp" android:height="22dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFB8C9D4" android:pathData="M3,11L12,3L21,11L19,11L19,20L14,20L14,14L10,14L10,20L5,20L5,11Z"/></vector>''',
'ic_signal.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="22dp" android:height="22dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFB8C9D4" android:pathData="M13,2L5,14L11,14L10,22L19,9L13,9Z"/></vector>''',
'ic_stats.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="22dp" android:height="22dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFB8C9D4" android:pathData="M4,20L8,20L8,12L4,12ZM10,20L14,20L14,7L10,7ZM16,20L20,20L20,3L16,3Z"/></vector>''',
'ic_settings.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="22dp" android:height="22dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFB8C9D4" android:pathData="M4,6L10,6L10,4L14,4L14,6L20,6L20,8L14,8L14,10L10,10L10,8L4,8ZM4,11L6,11L6,9L10,9L10,11L20,11L20,13L10,13L10,15L6,15L6,13L4,13ZM4,16L14,16L14,14L18,14L18,16L20,16L20,18L18,18L18,20L14,20L14,18L4,18Z"/></vector>''',
'ic_crypto_coin.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="30dp" android:height="30dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FF28D9F5" android:pathData="M12,2A10,10 0,1 0,12 22A10,10 0,1 0,12 2ZM12,6C14.1,6 15.8,6.8 17,8.1L15.3,9.7C14.5,8.9 13.4,8.5 12,8.5C10,8.5 8.5,10 8.5,12C8.5,14 10,15.5 12,15.5C13.4,15.5 14.5,15.1 15.3,14.3L17,15.9C15.8,17.2 14.1,18 12,18C8.6,18 6,15.4 6,12C6,8.6 8.6,6 12,6Z"/></vector>''',
'ic_signal_notify.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M13,2L5,14L11,14L10,22L19,9L13,9Z"/></vector>'''
}
for name,content in assets.items():(RES/name).write_text(content)

CHECKPOINT.write_text('''# SIGNALHUB_V3_CHECKPOINT_06 — Crypto Stability + Simple UI\n\n## Scope\nSignalHub is Crypto-only. Forex signal generation remains disabled. Two engines only: CRYPTO SCALP and CRYPTO SWING.\n\n## Parent\n- V3.13 final source: `d9af4382b7fe898bc055090e6fb9bd4e17c08407`\n- Working branch: `signalhub-v314-simple-ui-stability`\n- Backend target: `SIGNALHUB-V3-GATEWAY-3.14.0`\n- Android: `3.14.0` / versionCode 20\n\n## Production audit before tuning (2026-09-09)\nInfrastructure was healthy: 4 active Crypto signals / 4 unique symbols, 2 SCALP + 2 SWING, server monitor running, 460 provider quotes in the sampled monitor cycle, no monitor errors. Trading evidence was NOT proven. SCALP had only 4 resolved trades and all 4 were SL (-4R); SWING had 0 resolved trades. The SCALP sample is too small for a reliable win-rate estimate, but the four losses are a concrete warning and motivated this tuning.\n\n## V3.14 engine changes\n- No numeric setup score and no time/cooldown admission gate.\n- SCALP no longer accepts a generic trend/EMA pullback alone. New trades need liquidity sweep/reclaim, displacement+structure reclaim, or confirmed breakout evidence.\n- SWING requires H4/D1 direction plus H1 execution confirmation.\n- Secondary provider must positively confirm direction; neutral/opposing is not called confirmation.\n- Provider bid/ask is used for pending activation and exit tracking.\n- Pending setup cancels when its structural invalidation is broken before entry, not only after reaching the wider SL.\n- Higher turnover and tighter spread requirements for new entries.\n- Portfolio risk clusters prevent correlated meme-beta signals from filling the book: maximum one MEME exposure active at a time; max two in another risk cluster.\n- Performance remains resolved TP/SL only. No predicted win-rate is shown.\n\n## UX/UI\n- Four tabs only: Home / Signals / Stats / Settings. Alerts remain Android system notifications.\n- System font instead of monospace everywhere.\n- Vector app/logo/navigation/crypto assets are bundled locally.\n- Home is one-glance: connectivity, SCALP/SWING counts, real closed-trade evidence, latest signal.\n- Signal cards show only Symbol, Side, Order state, Current, Entry, SL, TP3, progress and one short regime line. Full TP ladder/reasoning stays in detail.\n- LIVE uses red/green risk gauge; pending LIMIT/STOP uses yellow distance-to-entry gauge.\n\n## Stability truth\n`/v3/stability` separates infrastructure health from trading evidence. Infrastructure can be STABLE while the strategy sample remains NOT_YET_PROVEN. Do not call the strategy statistically stable until each style has a meaningful resolved sample.\n\n## Rollback\nRollback source remains V3.13 branch/tag and APK if V3.14 production validation fails.\n''')

print('patched SignalHub V3.14 stability engine + simple UI + checkpoint')
