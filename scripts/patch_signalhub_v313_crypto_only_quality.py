from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
API=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
GRADLE=Path('signalhub-android/app/build.gradle')


def must_replace(text, old, new, label):
    if old not in text:
        raise SystemExit(f'{label}: pattern missing')
    return text.replace(old,new,1)

def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

# ---------------- Worker: CRYPTO ONLY ----------------
w=WORKER.read_text()
w=must_replace(w,"const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.12.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.13.0';",'worker version')
w=must_replace(w,"versionCode: 18,\n  versionName: '3.12.0',\n  title: 'SignalHub 3.12.0',","versionCode: 19,\n  versionName: '3.13.0',\n  title: 'SignalHub 3.13.0 Crypto Focus',",'release version')
w=must_replace(w,"artifactName: 'SignalHub-Android-v3.12.0',","artifactName: 'SignalHub-Android-v3.13.0-Crypto-Focus',",'artifact name')
w=w.replace("    'V3.12 fixes Crypto LIMIT/STOP lifecycle gaps: active crypto orders are now evaluated server-side by a Durable Object alarm without depending on the app or /crypto/tickers polling.',\n    'V3.12 pins every Crypto signal to its creation exchange and only that exchange may trigger its Entry/SL/TP lifecycle, preventing cross-exchange false or missed fills.',\n    'V3.12 adds always-on dual-market coverage: MT5 realtime packets atomically claim an empty FOREX/CRYPTO market and launch an immediate structure-qualified refill in the background.',",
"    'V3.13 removes Forex signal generation and turns SignalHub into a Crypto-only SCALP/SWING engine.',\n    'V3.13 separates Crypto SCALP and SWING quality rules, tightens spread/location/context/target-path checks, and prioritizes liquidity sweeps and aligned structure.',\n    'V3.13 keeps provider-pinned LIMIT/STOP lifecycle monitoring server-side and targets at least one qualified active idea per Crypto style when available.',")

old_policy="portfolioPolicy:{maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,minActivePerMarket:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'ALWAYS_ON_DUAL_MARKET',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S'}"
new_policy="portfolioPolicy:{maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true}"
w=must_replace(w,old_policy,new_policy,'judgment policy')
w=w.replace("name:'BOT_MARKET_JUDGMENT'","name:'CRYPTO_QUALITY_JUDGMENT'",1)
w=w.replace("qualityMode:'CLEAN_MARKET_STORY_NO_SCORE'","qualityMode:'CRYPTO_ONLY_STRICT_STRUCTURE_NO_SCORE'",1)

w=sub1(w,r"const STYLE_EXECUTION_POLICY = Object\.freeze\(\{.*?\n\}\);\n\nfunction validSignalStructure",r'''const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'liquidity sweep/reclaim first; otherwise fully aligned continuation or confirmed breakout',stopFocus:'micro swing/liquidity invalidation + ATR/spread buffer',targetFocus:'clean 15m/1h liquidity with minimum 2.15R geometry',holdModel:'short-horizon; reject extended/chasing market entries'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'H4+D1 alignment mandatory; H1 reclaim/pullback/rejoin or confirmed breakout',stopFocus:'H1/H4 invalidation outside liquidity + wider ATR buffer',targetFocus:'H4/D1 liquidity with minimum 2.75R geometry',holdModel:'multi-session; no H1-only directional trade'})
});

function validSignalStructure''','style policy')

w=w.replace("signal.market=String(market||signal.market||'FOREX').toUpperCase();","signal.market=String(market||signal.market||'CRYPTO').toUpperCase();",1)
w=must_replace(w,"  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN'));}","  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN')&&String(x.market||'').toUpperCase()==='CRYPTO');}",'DO active crypto only')
w=must_replace(w,"      const active=Object.values(reg).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN'));","      const active=this.activeRows(reg);",'DO active source')
w=must_replace(w,"      const market=String(s.market||'').toUpperCase(),style=String(s.style||'').toUpperCase(),symbol=canonical(s.symbol),policy=PORTFOLIO_POLICY;\n      const reject=reason=>({ok:true,accepted:false,id,status:s.status,reason,activeTotal:active.length,reg});",
"      const market=String(s.market||'').toUpperCase(),style=String(s.style||'').toUpperCase(),symbol=canonical(s.symbol),policy=PORTFOLIO_POLICY;\n      const reject=reason=>({ok:true,accepted:false,id,status:s.status,reason,activeTotal:active.length,reg});\n      if(market!=='CRYPTO')return reject('CRYPTO_ONLY_FOREX_DISABLED');",'DO reject forex')

old_port="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,minActivePerMarket:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'ALWAYS_ON_DUAL_MARKET',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S'});"
new_port="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:4,maxActivePerMarket:4,maxActivePerStyle:2,maxNewPerScan:1,minActivePerStyle:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_ONLY_STYLE_COVERAGE',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true});"
w=must_replace(w,old_port,new_port,'portfolio policy')

# Add liquidity metadata to Crypto technical snapshot.
w=must_replace(w,"tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,sweepHigh:a.sweepHigh",
"tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),sweepHigh:a.sweepHigh",'crypto technical liquidity')

# True secondary-exchange confirmation when available; never mislabeled because direct provider functions are used.
w=must_replace(w,"async function analyzeCryptoCandidate(t,style){try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildCryptoSetup(t,style,stats)}catch{return null;}}",
r'''async function analyzeCryptoCandidate(t,style){
  try{
    const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;
    const setup=buildCryptoSetup(t,style,stats);if(!setup)return null;
    const dir=String(setup.side||'').toUpperCase()==='LONG'?1:-1,contextInterval=intervalMap[style][1],primary=String(t.exchange||'').toUpperCase();
    const probes=[['BYBIT',bybitCandles],['OKX',okxCandles],['BINANCE',binanceCandles]].filter(x=>x[0]!==primary);
    for(const [provider,fn] of probes){
      try{const sec=tfStats(await fn(t.symbol,contextInterval));if(!sec)continue;setup.technicalAtIssue.crossProvider=provider;setup.technicalAtIssue.crossTrend=sec.trend;setup.technicalAtIssue.crossMomentum=sec.momentum;setup.crossProviderConfirmation=sec.trend!==-dir&&sec.momentum!==-dir;setup.rationale.push(`secondary ${provider} ${contextInterval} ${setup.crossProviderConfirmation?'confirms / not opposing':'opposes'} direction`);break;}catch{}
    }
    return setup;
  }catch{return null;}
}''','crypto cross provider')

# Replace entry assessment with Crypto-specific hard quality checks. No predicted score/win-rate.
w=sub1(w,r"function assessEntrySetup\(raw\)\{.*?\n\}\nfunction setupPriority",r'''function assessEntrySetup(raw){
  const s=raw||{},dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
  const entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{};
  const style=String(s.style||'SCALP').toUpperCase(),order=String(s.orderType||'').toUpperCase(),regime=String(s.marketRegime||''),expectedStyle=style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE';
  const levels=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3;
  const trends=Array.isArray(tech.tfTrend)?tech.tfTrend.map(signOf):[];
  const contextAligned=style==='SWING'?trends.length>=3&&trends[1]===dir&&trends[2]===dir:trends.length>=3&&trends[1]!==-dir&&trends[2]!==-dir&&(trends[1]===dir||trends[2]===dir);
  const ext=Math.abs(Number(tech.extensionAtr||0)),maxMarketExt=style==='SWING'?.18:.24,risk=Math.abs(entry-sl),triggerDistance=risk>0&&src>0?Math.abs(src-entry)/risk:999;
  const marketLocation=order==='MARKET'?(regime.includes('LIQUIDITY')||ext<=maxMarketExt):order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false;
  const limitMax=style==='SWING'?1.05:.95,stopMax=style==='SWING'?.60:.55,pendingReachable=order==='MARKET'||(order==='LIMIT'?triggerDistance<=limitMax:order==='STOP'?triggerDistance<=stopMax:false);
  const invalidation=Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry),rr=Number(s.targetRR||0),rrQuality=rr>=(style==='SWING'?2.75:2.15);
  const spread=Number(tech.spreadBps||0),spreadQuality=spread>=0&&spread<=(style==='SWING'?20:10),turnover=Number(tech.turnover24h||0),liquidityQuality=turnover>=(style==='SWING'?5_000_000:8_000_000);
  const rsi=Number(tech.rsi||50),momentumSanity=dir>0?rsi<=72:rsi>=28,crossProvider=s.crossProviderConfirmation!==false;
  const rationale=Array.isArray(s.rationale)?s.rationale:[],wide=String(s.executionCaution||'NORMAL').toUpperCase()==='WIDE';
  const regimeQuality=style==='SWING'?(regime.includes('HTF_')||regime.includes('LIQUIDITY')):(regime.includes('LIQUIDITY')||regime.includes('TREND')||regime.includes('BREAKOUT'));
  const checks={
    cryptoOnly:String(s.market||'CRYPTO').toUpperCase()==='CRYPTO',
    cleanStory:typeof s.marketStory==='string'&&s.marketStory.trim().length>=18,
    styleModel:s.styleExecutionModel===expectedStyle,
    contextAligned,
    regimeQuality,
    entryLocation:src>0&&marketLocation,
    pendingReachable,
    invalidation,
    targetPath:levels,
    rrQuality,
    spreadQuality,
    liquidityQuality,
    momentumSanity,
    crossProvider,
    executionModel:typeof s.entryModel==='string'&&s.entryModel.length>8&&typeof s.slModel==='string'&&s.slModel.length>8&&typeof s.tpModel==='string'&&s.tpModel.length>8,
    rationaleComplete:rationale.length>=4,
    executionConditions:!wide,
    liveSource:src>0
  };
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'CRYPTO_HARD_QUALITY_CHECKS_NO_PREDICTED_SCORE',checks,failed,geometry:{extensionAtr:Number(ext.toFixed(3)),triggerDistanceR:Number(triggerDistance.toFixed(3)),maxMarketExtensionAtr:maxMarketExt,minTargetRR:style==='SWING'?2.75:2.15,maxSpreadBps:style==='SWING'?20:10,minTurnover24h:style==='SWING'?5_000_000:8_000_000}};
}
function setupPriority''','crypto assessment')

w=sub1(w,r"function setupPriority\(s\)\{.*?\n\}\nfunction compareSetupPriority",r'''function setupPriority(s){
  const r=String(s.marketRegime||''),family=r.includes('LIQUIDITY')?0:r.includes('HTF_TREND')?1:r.includes('TREND')?2:r.includes('BREAKOUT')?3:4;
  const spread=Number(s?.technicalAtIssue?.spreadBps||999),ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),rr=Number(s.targetRR||0),turnover=Number(s?.technicalAtIssue?.turnover24h||0);
  return [family,spread,ext,-rr,-turnover];
}
function compareSetupPriority''','priority')

w=must_replace(w,"async function getActiveBook(env){\n  const out=[];for(const market of ['FOREX','CRYPTO'])for(const style of ['SCALP','SWING']){const rows=await getV31Signals(env,market,style);for(const s of rows)if((s.status==='PENDING'||s.status==='OPEN')&&String(s.engineVersion||'')===V3_VERSION)out.push(s);}return out;\n}",
"async function getActiveBook(env){\n  const out=[];for(const style of ['SCALP','SWING']){const rows=await getV31Signals(env,'CRYPTO',style);for(const s of rows)if((s.status==='PENDING'||s.status==='OPEN')&&String(s.engineVersion||'')===V3_VERSION)out.push(s);}return out;\n}",'active book crypto only')
w=w.replace('REPLACED_BY_V312_ALWAYS_ON_DUAL_MARKET','REPLACED_BY_V313_CRYPTO_ONLY_QUALITY')
w=w.replace('V312_ACTIVE_BOOK_RESET','V313_CRYPTO_ONLY_RESET')

w=sub1(w,r"async function scanCrypto\(env,style\)\{.*?\n\}\n\nasync function exnessQuoteMap",r'''async function scanCrypto(env,style){
  style=String(style||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const trackerEvents=await retireAllLegacyActiveSignals(env);
  const snap=await loadCryptoSnapshot(env);if(snap.live===false)return {ok:true,version:V3_VERSION,market:'CRYPTO',style,status:'NO_FRESH_CRYPTO_SNAPSHOT',created:0,provider:snap.provider,live:false,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};
  const all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),styleEmpty=Number(portfolio.styles?.[style]||0)<PORTFOLIO_POLICY.minActivePerStyle;
  const rankedLimit=style==='SCALP'?(styleEmpty?22:16):(styleEmpty?18:14),minTurnover=style==='SCALP'?8_000_000:5_000_000,maxSpread=style==='SCALP'?12:24;
  const liquid=all.filter(x=>Number(x.lastPrice)>0&&Number(x.turnover24h||0)>=minTurnover&&(x.spreadBps==null||Number(x.spreadBps)<=maxSpread));
  const ranked=liquid.sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,rankedLimit);
  const rawAnalyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean),assessed=rawAnalyses.map(x=>({...x,entryAssessment:assessEntrySetup(x)})),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'Crypto-only quality engine. SCALP and SWING use separate hard structure rules; no predicted win-rate or numeric score is fabricated.'};
}

async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    if(Number(p.styles?.[style]||0)>=PORTFOLIO_POLICY.minActivePerStyle)continue;
    attempted.push(style);await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {attempted,portfolio:p};
}

async function exnessQuoteMap''','scan crypto')

# Crypto-only public partitions.
w=sub1(w,r"async function unifiedSignals\(url,env\)\{.*?\n\}\n\nasync function unifiedPerformance",r'''async function unifiedSignals(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',status=String(url.searchParams.get('status')||'active').toLowerCase(),limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120)));
  let rows=await getV31Signals(env,market,style);rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  if(status==='active'&&rows.length===0&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(scanCrypto(env,style)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',market,style,partitionKey:`CRYPTO:${style}`,status,count:rows.length,dataHealth:{provider:'LIVE_CRYPTO_PROVIDER_PINNED',state:'SERVER_MONITORED'},decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
}

async function unifiedPerformance''','unified signals')

w=sub1(w,r"async function unifiedPerformance\(url,env\)\{.*?\n\}\nasync function scanRoute",r'''async function unifiedPerformance(url,env){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=await getV31Signals(env,market,style),active=rows.filter(s=>s.status==='PENDING'||s.status==='OPEN'),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',market,style,performance:{total:rows.length,active:active.length,pending:active.filter(s=>s.status==='PENDING').length,open:active.filter(s=>s.status==='OPEN').length,resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,winRateLabel:resolved.length?`${wr.toFixed(1)}% (${tp}/${resolved.length})`:'CHƯA CÓ MẪU'}});
}
async function scanRoute''','unified performance')

w=sub1(w,r"async function scanRoute\(url,env,ctx\)\{.*?\n\}\nasync function v3Status",r'''async function scanRoute(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';return json(await scanCrypto(env,style));
}
async function v3Status''','scan route')

w=sub1(w,r"async function v3Status\(env\)\{.*?\n\}\nasync function handleV3",r'''async function v3Status(env,ctx){
  const portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env),missing=['SCALP','SWING'].filter(st=>Number(portfolio.styles?.[st]||0)<PORTFOLIO_POLICY.minActivePerStyle);
  if(missing.length&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',service:'SignalHub Crypto SCALP/SWING gateway',checkpoint:CHECKPOINT,app:V31_RELEASE,crypto:{priceAuthority:'PROVIDER_PINNED_BYBIT_PREFERRED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'STRICT_5M_15M_1H',swing:'STRICT_1H_4H_1D',pendingLifecycle:'DURABLE_OBJECT_ALARM_1S',crossProviderContextCheck:true},engines:{cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},forexDisabled:true,portfolio,missingStyles:missing,cryptoMonitor,decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'});
}
async function handleV3''','status')

w=sub1(w,r"async function handleV3\(req,env,ctx\)\{.*?\n\}\n\nexport default",r'''async function handleV3(req,env,ctx){
  const url=new URL(req.url);if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'content-type, authorization, x-signalhub-bridge','access-control-allow-methods':'GET,POST,OPTIONS'}});
  try{
    if(url.pathname==='/v3/status'&&req.method==='GET')return v3Status(env,ctx);
    if(url.pathname==='/v3/app-version'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',checkpoint:CHECKPOINT,app:V31_RELEASE});
    if(url.pathname.startsWith('/v3/mt5/')&&req.method==='POST')return json({ok:true,version:V3_VERSION,ignored:true,mode:'CRYPTO_ONLY_QUALITY',reason:'FOREX_BRANCH_DISABLED'});
    if(url.pathname.startsWith('/v3/forex/'))return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
    if(url.pathname==='/v3/crypto/tickers'&&req.method==='GET')return cryptoTickers(url,env);
    if(url.pathname==='/v3/crypto/monitor'&&req.method==='GET'){const kick=url.searchParams.get('kick')==='1'?await kickCryptoServerMonitor(env):null;if(ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',status:await cryptoServerMonitorStatus(env),kick,portfolio:await realtimePortfolioSnapshot(env)});}
    if(url.pathname==='/v3/portfolio'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',portfolio:await realtimePortfolioSnapshot(env),policy:PORTFOLIO_POLICY});
    if(url.pathname==='/v3/crypto/discovery'&&req.method==='GET')return cryptoDiscovery(url,env);
    if(url.pathname==='/v3/scan'&&req.method==='GET')return scanRoute(url,env,ctx);
    if(url.pathname==='/v3/signals'&&req.method==='GET')return unifiedSignals(url,env,ctx);
    if(url.pathname==='/v3/performance'&&req.method==='GET')return unifiedPerformance(url,env);
    if(url.pathname==='/v3/decision-policy'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',policy:MARKET_JUDGMENT_POLICY,stylePolicy:STYLE_EXECUTION_POLICY,portfolioPolicy:PORTFOLIO_POLICY});
    return null;
  }catch(e){const msg=String(e?.message||e),code=msg==='INVALID_JSON'?400:msg==='PAYLOAD_TOO_LARGE'?413:503;return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:msg},code);}
}

export default''','handle v3')

w=sub1(w,r"export default \{.*?\n\};\s*$",r'''export default {
  async fetch(req,env,ctx){const v3=await handleV3(req,env,ctx);if(v3)return v3;return json({ok:false,version:V3_VERSION,mode:'CRYPTO_ONLY_QUALITY',error:'CRYPTO_ONLY_ENDPOINT_NOT_FOUND'},404);},
  async scheduled(event,env,ctx){ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));},
};''','export crypto only')
WORKER.write_text(w)

# ---------------- Android: only CRYPTO SCALP / SWING ----------------
a=ACT.read_text()
a=must_replace(a,'private static final String APP_VERSION="3.12.0";','private static final String APP_VERSION="3.13.0";','app version')
a=must_replace(a,'private String screen="HOME",style="SCALP",filter="ALL";','private String screen="HOME",style="SCALP",filter="CRYPTO";','default filter')
a=must_replace(a,'        long streamAge=fxStreamLastMs==0?Long.MAX_VALUE:System.currentTimeMillis()-fxStreamLastMs;\n        if(streamAge>1500)refreshForexLive();\n        refreshCryptoLive();','        refreshCryptoLive();','main loop crypto only')
a=must_replace(a,'    @Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);connectForexStream();main.removeCallbacks(loop);main.post(loop);}\n    @Override protected void onPause(){resumed=false;main.removeCallbacks(loop);closeForexStream();super.onPause();}',
'    @Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);main.removeCallbacks(loop);main.post(loop);}\n    @Override protected void onPause(){resumed=false;main.removeCallbacks(loop);super.onPause();}','resume crypto only')
a=must_replace(a,'TextView logo=tv("SIGNALHUB",22,TEXT,true);subtitle=tv("SCALP ≠ SWING • ALWAYS-ON DUAL MARKET • REALTIME • V3.12",8,MUTED,true);',
'TextView logo=tv("SIGNALHUB CRYPTO",22,TEXT,true);subtitle=tv("CRYPTO ONLY • SCALP ≠ SWING • REALTIME • V3.13",8,MUTED,true);','header')
a=sub1(a,r"        LinearLayout live=row\(\);fxLive=chip\(\"EXNESS • OFFLINE\",RED\);cryptoLive=chip\(\"CRYPTO • OFFLINE\",RED\);.*?head\.addView\(live\);",
'''        LinearLayout live=row();fxLive=chip("FOREX • DISABLED",MUTED);cryptoLive=chip("CRYPTO • OFFLINE",RED);
        LinearLayout.LayoutParams lp2=new LinearLayout.LayoutParams(0,-2,1f);lp2.setMargins(0,dp(8),0,0);live.addView(cryptoLive,lp2);head.addView(live);''','live header')
a=sub1(a,r"        LinearLayout filters=row\(\);String\[\] fs=\{\"ALL\",\"XAU\",\"FX\",\"OIL\",\"CRYPTO\"\};.*?signalControls\.addView\(filters\);head\.addView\(signalControls\);",
'        head.addView(signalControls);','remove market filters')

a=sub1(a,r"    private void loadSignalPartitions\(String st\)\{.*?\n    \}\n\n    private String fingerprint",r'''    private void loadSignalPartitions(String st){
        boolean changed=false;String m="CRYPTO";
        try{
            JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market=CRYPTO&style="+st+"&status=active&limit=100"));
            JSONArray arr=root.optJSONArray("signals");if(arr==null)arr=new JSONArray();String key="CRYPTO:"+st,fp=fingerprint(arr),old=signalFingerprints.put(key,fp);signalCache.put(key,arr);lastApiOkMs=System.currentTimeMillis();if(old==null||!old.equals(fp))changed=true;
            try{JSONObject perf=new JSONObject(ApiClient.get("/v3/performance?market=CRYPTO&style="+st)).optJSONObject("performance");if(perf!=null)perfCache.put(key,perf);}catch(Throwable ignored){}
        }catch(Throwable ignored){}
        if(changed&&style.equals(st)&&screen.equals("SIGNALS")&&!detail)main.post(()->renderSignals(false));
    }

    private String fingerprint''','load partitions')

a=sub1(a,r"    private void kickScanIfDue\(\)\{.*?\n    \}\n\n    private List<JSONObject> collectSignals",r'''    private void kickScanIfDue(){
        if(!screen.equals("SIGNALS")||!scanBusy.compareAndSet(false,true))return;
        final String st=style;io.execute(()->{try{long now=System.currentTimeMillis();String key="CRYPTO:"+st;long last=lastScanAt.getOrDefault(key,0L);if(now-last>=SCAN_MS){try{ApiClient.get("/v3/scan?market=CRYPTO&style="+st);lastScanAt.put(key,System.currentTimeMillis());}catch(Throwable ignored){}}}finally{scanBusy.set(false);}});
    }

    private List<JSONObject> collectSignals''','scan only crypto')
a=sub1(a,r"    private List<JSONObject> collectSignals\(\)\{.*?\n    \}\n    private boolean acceptFilter\(JSONObject s,String fallbackMarket\)\{.*?\n    \}",r'''    private List<JSONObject> collectSignals(){
        List<JSONObject> out=new ArrayList<>();JSONArray arr=signalCache.get("CRYPTO:"+style);if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject s=arr.optJSONObject(i);if(s!=null)out.add(s);}out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }
    private boolean acceptFilter(JSONObject s,String fallbackMarket){return "CRYPTO".equalsIgnoreCase(s.optString("market",fallbackMarket));}''','collect crypto')
a=a.replace('subtitle.setText("EXNESS REALTIME • LIVE / LIMIT / STOP");','subtitle.setText("CRYPTO REALTIME • SCALP / SWING • LIVE / LIMIT / STOP");')
a=a.replace('subtitle.setText("REALTIME CONTROL CENTER • EXNESS + SIGNAL ENGINE");','subtitle.setText("CRYPTO EXECUTION INTELLIGENCE • QUALITY-FIRST");')
a=a.replace('h.addView(chip(fxState,stateColor(fxState)));','h.addView(chip(cryptoProvider+" • "+cryptoState,stateColor(cryptoState)));',1)
a=a.replace('conn.addView(statusRow("Quote Feed • Exness MT5",fxState));conn.addView(statusRow("Quote Feed • "+cryptoProvider,cryptoState));','conn.addView(statusRow("Quote Feed • "+cryptoProvider,cryptoState));',1)
a=must_replace(a,'private void loadAllPerformance(){boolean changed=false;for(String m:new String[]{"FOREX","CRYPTO"})for(String st:new String[]{"SCALP","SWING"}){try{JSONObject p=new JSONObject(ApiClient.get("/v3/performance?market="+m+"&style="+st)).optJSONObject("performance");if(p!=null){String k=m+":"+st,old=perfCache.containsKey(k)?perfCache.get(k).toString():"";perfCache.put(k,p);if(!old.equals(p.toString()))changed=true;lastApiOkMs=System.currentTimeMillis();}}catch(Throwable ignored){}}if(changed&&screen.equals("STATS"))main.post(()->renderStats(false));}',
'private void loadAllPerformance(){boolean changed=false;for(String st:new String[]{"SCALP","SWING"}){try{JSONObject p=new JSONObject(ApiClient.get("/v3/performance?market=CRYPTO&style="+st)).optJSONObject("performance");if(p!=null){String k="CRYPTO:"+st,old=perfCache.containsKey(k)?perfCache.get(k).toString():"";perfCache.put(k,p);if(!old.equals(p.toString()))changed=true;lastApiOkMs=System.currentTimeMillis();}}catch(Throwable ignored){}}if(changed&&screen.equals("STATS"))main.post(()->renderStats(false));}','performance crypto')
a=a.replace('for(String m:new String[]{"FOREX","CRYPTO"})for(String st:new String[]{"SCALP","SWING"})content.addView(perfCard(m,st));','for(String st:new String[]{"SCALP","SWING"})content.addView(perfCard("CRYPTO",st));',1)

a=sub1(a,r"    private void renderSources\(boolean animate\)\{.*?\n\n    private void loadSystemStatus",r'''    private void renderSources(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CRYPTO DATA • FRESHNESS • CONNECTION HEALTH");content.addView(tv("NGUỒN DỮ LIỆU CRYPTO",16,TEXT,true));LinearLayout cr=card();cr.addView(tv("CRYPTO • "+cryptoProvider,13,TEXT,true));cr.addView(line("STATUS",cryptoState,stateColor(cryptoState)));cr.addView(line("SYMBOLS",String.valueOf(cryptoCount),TEXT));cr.addView(tv("Bybit ưu tiên; OKX/Binance fallback được gắn đúng nguồn. Entry/SL/TP lifecycle luôn dùng đúng executionPriceAuthority của từng tín hiệu.",9,MUTED,false));content.addView(cr);LinearLayout rule=card();rule.addView(tv("QUALITY + DATA INTEGRITY",12,CYAN,true));rule.addView(tv("SCALP và SWING tách riêng. Không giả win-rate dự đoán; chỉ thống kê TP/SL đã đóng. Quote lỗi không được giả thành LIVE.",10,MUTED,false));content.addView(rule);};if(animate)swap(body);else body.run();}

    private void loadSystemStatus''','sources')
a=sub1(a,r"    private void renderSystem\(boolean animate\)\{.*?\n    private View statusRow",r'''    private void renderSystem(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CRYPTO SYSTEM STATUS • SIGNAL ENGINE • LIVE FEED");content.addView(tv("HỆ THỐNG CRYPTO",16,TEXT,true));LinearLayout c=card();c.addView(statusRow("Crypto Signal Engine",systemState));c.addView(statusRow("Quote Feed • "+cryptoProvider,cryptoState));c.addView(statusRow("Push Monitor",monitorStarted?"RUNNING":"OFFLINE"));c.addView(statusRow("API Connectivity",lastApiOkMs>0&&System.currentTimeMillis()-lastApiOkMs<15000?"ONLINE":"DEGRADED"));content.addView(c);LinearLayout meta=card();meta.addView(line("APP VERSION",APP_VERSION,BLUE));if(systemStatus!=null){meta.addView(line("BACKEND",systemStatus.optString("version","—"),TEXT));meta.addView(line("MODE",systemStatus.optString("mode","—"),CYAN));}meta.addView(line("LAST API SYNC",lastApiOkMs==0?"—":relativeAge(System.currentTimeMillis()-lastApiOkMs),MUTED));content.addView(meta);};if(animate)swap(body);else body.run();}
    private View statusRow''','system screen')

a=sub1(a,r"    private void renderSettings\(boolean animate\)\{.*?\n    \};if\(animate\)swap\(body\);else body\.run\(\);\}",r'''    private void renderSettings(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CÀI ĐẶT • CRYPTO DATA • QUALITY ENGINE");content.addView(tv("CÀI ĐẶT",16,TEXT,true));
        LinearLayout notify=card();notify.addView(tv("🔔  THÔNG BÁO",12,TEXT,true));notify.addView(statusRow("Push Monitor",monitorStarted?"RUNNING":"OFFLINE"));notify.addView(statusRow("Quyền thông báo",notifyPermission()?"ONLINE":"OFFLINE"));if(!monitorStarted){Button b=button("BẬT PUSH MONITOR",true,v->ensureMonitor(true));notify.addView(b,new LinearLayout.LayoutParams(-1,dp(42)));}content.addView(notify);
        LinearLayout source=card();source.addView(tv("◉  NGUỒN DỮ LIỆU CRYPTO",12,TEXT,true));source.addView(statusRow(cryptoProvider,cryptoState));source.addView(line("Crypto symbols",String.valueOf(cryptoCount),TEXT));source.addView(line("Price authority","Provider-pinned per signal",CYAN));content.addView(source);
        LinearLayout sys=card();sys.addView(tv("⚙  HỆ THỐNG",12,TEXT,true));sys.addView(statusRow("Crypto Signal Engine",systemState));sys.addView(statusRow("API Connectivity",lastApiOkMs>0&&System.currentTimeMillis()-lastApiOkMs<15000?"ONLINE":"DEGRADED"));sys.addView(line("App version",APP_VERSION,BLUE));if(systemStatus!=null){sys.addView(line("Backend",systemStatus.optString("version","—"),TEXT));sys.addView(line("Mode",systemStatus.optString("mode","—"),CYAN));}content.addView(sys);
        LinearLayout ui=card();ui.addView(tv("✦  CRYPTO QUALITY ENGINE",12,TEXT,true));ui.addView(line("SCALP","5m / 15m / 1h",CYAN));ui.addView(line("SWING","1h / 4h / 1d",BLUE));ui.addView(line("Entry Routing","MARKET / LIMIT / STOP tự động",TEXT));ui.addView(line("Pending Trigger","Server monitor 1s • provider-pinned",GREEN));ui.addView(line("Quality","Structure + context + spread + liquidity + RR",CYAN));ui.addView(line("Coverage","Mục tiêu ≥1 setup đạt chuẩn mỗi style",GREEN));ui.addView(line("Forex","ĐÃ TẮT",MUTED));content.addView(ui);
    };if(animate)swap(body);else body.run();}''','settings')

a=sub1(a,r"    private void updateConnectionViews\(\)\{.*?\}\n    private void updateAllPriceViews",r'''    private void updateConnectionViews(){int cc=stateColor(cryptoState);cryptoLive.setText(cryptoProvider+" • "+cryptoState);cryptoLive.setTextColor(cc);cryptoLive.setBackground(shape(Color.argb(28,Color.red(cc),Color.green(cc),Color.blue(cc)),9,cc));}
    private void updateAllPriceViews''','connection view')
a=a.replace('String id=e.getKey(),m=viewMarkets.getOrDefault(id,"FOREX");','String id=e.getKey(),m=viewMarkets.getOrDefault(id,"CRYPTO");')
a=a.replace('String state=m.equals("FOREX")?fxState:cryptoState;','String state=cryptoState;')
ACT.write_text(a)

# ---------------- Android foreground monitor ----------------
m=MON.read_text()
m=m.replace('startForeground(FOREGROUND_ID,monitor("Đang đồng bộ 4 luồng FOREX/CRYPTO • SCALP/SWING"));','startForeground(FOREGROUND_ID,monitor("CRYPTO ONLY • đang đồng bộ SCALP / SWING"));')
m=sub1(m,r"    private void syncAll\(\)\{.*?\n    \}\n\n    private void process",r'''    private void syncAll(){
        try{ApiClient.getLive("/v3/crypto/tickers?limit=1000");}catch(Throwable ignored){}
        int active=0,failed=0;
        for(String style:new String[]{"SCALP","SWING"}){
            int styleActive=0;
            try{
                JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market=CRYPTO&style="+style+"&status=all&limit=120"));JSONArray arr=root.optJSONArray("signals");
                if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject s=arr.optJSONObject(i);if(s==null)continue;String st=s.optString("status","");if("PENDING".equals(st)||"OPEN".equals(st)){active++;styleActive++;}process("CRYPTO",style,s,"SERVER_MONITORED");}
            }catch(Throwable e){failed++;}
            if(styleActive==0)try{ApiClient.get("/v3/scan?market=CRYPTO&style="+style);}catch(Throwable ignored){}
        }
        NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(n!=null){String text=failed==0?"CRYPTO LIVE • "+active+" tín hiệu SCALP/SWING đang theo dõi":"DEGRADED • "+failed+"/2 luồng đang nối lại • "+active+" active";n.notify(FOREGROUND_ID,monitor(text));}
    }

    private void process''','monitor sync')
m=m.replace('notifySignal(s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP EXNESS":"ACTIVE",market,style,s,dataState,id+":open")','notifySignal("ENTRY ĐÃ KÍCH HOẠT",market,style,s,dataState,id+":open")')
m=m.replace('.setContentTitle("SignalHub V3.11 • ATOMIC QUALITY BOOK LIVE")','.setContentTitle("SignalHub V3.13 • CRYPTO QUALITY LIVE")')
MON.write_text(m)

# ---------------- Client / version ----------------
api=API.read_text().replace('SignalHub-Android/3.12.0-always-on-dual-market','SignalHub-Android/3.13.0-crypto-only-quality')
API.write_text(api)

g=GRADLE.read_text().replace('versionCode 18','versionCode 19').replace("versionName '3.12.0'","versionName '3.13.0'")
GRADLE.write_text(g)

print('patched SignalHub V3.13 crypto-only quality engine')
