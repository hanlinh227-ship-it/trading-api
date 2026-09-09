from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
API=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
GRADLE=Path('signalhub-android/app/build.gradle')


def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

w=WORKER.read_text()
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.9.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.10.0';")
w=w.replace("versionCode: 15,\n  versionName: '3.9.0',\n  title: 'SignalHub 3.9.0',","versionCode: 16,\n  versionName: '3.10.0',\n  title: 'SignalHub 3.10.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.9.0',","artifactName: 'SignalHub-Android-v3.10.0',")
w=w.replace("    'V3.9 Clean Market Story removes permissive transition entries and requires a coherent structure/liquidity narrative before the bot emits an order.',","    'V3.10 Disciplined Book keeps the clean market story model and adds portfolio-level concurrency discipline plus a mandatory hard-check assessment for every order.',\n    'Only one active idea is allowed per symbol across SCALP/SWING. The whole app is capped at 6 active ideas, 4 per market, 3 per style and 2 new ideas per scan.',\n    'No numeric score is used as an admission gate: orders pass or fail explicit structure, context, entry-location, invalidation and target-path checks.',\n    'V3.9 Clean Market Story removes permissive transition entries and requires a coherent structure/liquidity narrative before the bot emits an order.',")
w=w.replace("  lifecycleSource:'DURABLE_OBJECT_REALTIME_SINGLE_SOURCE'","  lifecycleSource:'DURABLE_OBJECT_REALTIME_SINGLE_SOURCE',\n  entryAssessment:'HARD_STRUCTURE_CHECKS_NO_NUMERIC_SCORE',\n  portfolioPolicy:{maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,oneActivePerSymbolAcrossStyles:true}")

w=w.replace("function activePointer(market,style,symbol){return `v31:active:${market}:${style}:${symbol}`;}","function activePointer(market,style,symbol){return `v31:active:${market}:${style}:${symbol}`;}\nfunction activeAnyPointer(market,symbol){return `v31:active:any:${market}:${symbol}`;}")

new_write=r'''async function writeV31Signal(env,s){
  const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});
  const active=s.status==='PENDING'||s.status==='OPEN',styleKey=activePointer(s.market,s.style,s.symbol),anyKey=activeAnyPointer(s.market,s.symbol);
  if(active){await env.SIGNALS_KV.put(styleKey,s.id,{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put(anyKey,s.id,{expirationTtl:SIGNAL_TTL});}
  else{await env.SIGNALS_KV.delete(styleKey);const anyId=await env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===s.id)await env.SIGNALS_KV.delete(anyKey);}
  await syncRealtimeSignal(env,s,key);
}'''
w=sub1(w,r"async function writeV31Signal\(env,s\)\{.*?\}\nasync function trackV31Signals",new_write+"\nasync function trackV31Signals",'write signal global pointer')

# Realtime close/cancel must clear both the style pointer and the cross-style symbol pointer.
w=w.replace("if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});if(!active)await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);}","if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});if(active){await this.env.SIGNALS_KV.put(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`,clean.id,{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.put(`v31:active:any:${clean.market}:${clean.symbol}`,clean.id,{expirationTtl:SIGNAL_TTL});}else{await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);const anyId=await this.env.SIGNALS_KV.get(`v31:active:any:${clean.market}:${clean.symbol}`);if(!anyId||anyId===clean.id)await this.env.SIGNALS_KV.delete(`v31:active:any:${clean.market}:${clean.symbol}`);}}")

policy_block=r'''const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,oneActivePerSymbolAcrossStyles:true});
function signOf(v){const n=Number(v);return n>0?1:n<0?-1:0;}
function assessEntrySetup(raw){
  const s=raw||{},dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
  const entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{};
  const order=String(s.orderType||'').toUpperCase(),regime=String(s.marketRegime||''),expectedStyle=s.style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE';
  const levels=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3;
  const contextSeries=Array.isArray(tech.tfTrend)?tech.tfTrend:Array.isArray(tech.recommend)?tech.recommend:[];
  const contextTail=contextSeries.slice(1).map(signOf).filter(Boolean),contextAligned=contextTail.length>0&&contextTail.every(x=>x!==-dir);
  const ext=Math.abs(Number(tech.extensionAtr||0));
  const marketLocation=order==='MARKET'?(regime.includes('LIQUIDITY')||ext<=.40):order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false;
  const invalidation=Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry);
  const checks={
    cleanStory:typeof s.marketStory==='string'&&s.marketStory.trim().length>=18,
    styleModel:s.styleExecutionModel===expectedStyle,
    contextAligned,
    entryLocation:src>0&&marketLocation,
    invalidation,
    targetPath:levels,
    executionModel:typeof s.entryModel==='string'&&s.entryModel.length>8&&typeof s.slModel==='string'&&s.slModel.length>8&&typeof s.tpModel==='string'&&s.tpModel.length>8,
    liveSource:src>0
  };
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'HARD_STRUCTURE_CHECKS_NO_NUMERIC_SCORE',checks,failed};
}
function setupPriority(s){
  const r=String(s.marketRegime||'');
  const family=r.includes('LIQUIDITY')?0:r.includes('HTF_TREND')?1:r.includes('TREND')?2:r.includes('BREAKOUT')?3:4;
  const ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),rr=Number(s.targetRR||0);
  return [family,ext,-rr];
}
function compareSetupPriority(a,b){const x=setupPriority(a),y=setupPriority(b);for(let i=0;i<x.length;i++){if(x[i]!==y[i])return x[i]-y[i];}return String(a.symbol).localeCompare(String(b.symbol));}
async function getActiveBook(env){
  const out=[];for(const market of ['FOREX','CRYPTO'])for(const style of ['SCALP','SWING']){const rows=await getV31Signals(env,market,style);for(const s of rows)if(s.status==='PENDING'||s.status==='OPEN')out.push(s);}return out;
}
async function retireLegacyActiveSignals(env,market,style){
  if(!env?.SIGNALS_KV)return[];const all=await getV31Signals(env,market,style),events=[],at=nowIso();
  for(const s of all){
    if((s.status!=='PENDING'&&s.status!=='OPEN')||String(s.engineVersion||'')===V3_VERSION)continue;
    s.status='CANCELLED';s.entryState='CANCELLED';s.lifecycle='REPLACED_BY_V310_DISCIPLINED_BOOK';s.outcome='CONTEXT_REFRESH';s.cancelledAt=at;s.resolution='V310_ACTIVE_BOOK_RESET';s.lastCheckedAt=at;s.resultR=null;s.brokerAction='NONE_SIGNAL_FEED_ONLY';
    await writeV31Signal(env,s);events.push({type:'CANCELLED',id:s.id,symbol:s.symbol,reason:s.lifecycle});
  }
  return events;
}
async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];
  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(x=>{const assessment=assessEntrySetup(x);return {...x,entryAssessment:assessment};}).filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const activeTotal=()=>book.length,marketCount=()=>book.filter(x=>x.market===market).length,styleCount=()=>book.filter(x=>x.style===style).length;
  for(const rawSetup of candidates){
    if(made.length>=PORTFOLIO_POLICY.maxNewPerScan||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||marketCount()>=PORTFOLIO_POLICY.maxActivePerMarket||styleCount()>=PORTFOLIO_POLICY.maxActivePerStyle)break;
    const setup=stampMarketJudgment({...rawSetup},market,style);if(!validSignalStructure(setup))continue;
    if(book.some(x=>x.market===market&&x.symbol===setup.symbol))continue;
    const anyPtr=await env.SIGNALS_KV.get(activeAnyPointer(market,setup.symbol));if(anyPtr)continue;
    const issuedAt=nowIso(),id=`V310-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,portfolioPolicy:PORTFOLIO_POLICY},market,style);
    await writeV31Signal(env,s);made.push(s);book.push(s);
  }
  return made;
}'''

w=sub1(w,r"async function retireLegacyPendingSignals\(env,market,style\)\{.*?\n\}\nasync function maybeCreateV31\(env,market,style,setups\)\{.*?\n\}",policy_block,'disciplined book functions')

# Every scan retires old active ideas first, assesses every new candidate, then portfolio policy decides whether a passed setup may occupy a slot.
w=w.replace("const trackerEvents=await retireLegacyPendingSignals(env,'CRYPTO',style);\n  const analyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean);\n  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);\n  return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,deepAnalyzed:ranked.length,actionable:analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time/RR admission gate. The bot emits an order only when it can form a coherent market story; otherwise NO TRADE.'};",
"const trackerEvents=await retireLegacyActiveSignals(env,'CRYPTO',style);\n  const rawAnalyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean),assessed=rawAnalyses.map(x=>({...x,entryAssessment:assessEntrySetup(x)})),analyses=assessed.filter(x=>x.entryAssessment.verdict==='PASS');\n  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);\n  return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'Every order must PASS hard structure checks. No numeric score gate. Portfolio caps prevent duplicate and excessive simultaneous entries.'};")

w=w.replace("const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await retireLegacyPendingSignals(env,'FOREX',style),setups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),created=await maybeCreateV31(env,'FOREX',style,setups);\n  return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,actionable:setups.length,noTrade:Math.max(0,rows.length-setups.length),created:created.length,newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY};",
"const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await retireLegacyActiveSignals(env,'FOREX',style),rawSetups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),assessed=rawSetups.map(x=>({...x,entryAssessment:assessEntrySetup(x)})),setups=assessed.filter(x=>x.entryAssessment.verdict==='PASS'),created=await maybeCreateV31(env,'FOREX',style,setups);\n  return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,evaluated:rawSetups.length,actionable:setups.length,rejectedByAssessment:rawSetups.length-setups.length,noTrade:Math.max(0,rows.length-setups.length),created:created.length,portfolioBlocked:Math.max(0,setups.length-created.length),newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};")

WORKER.write_text(w)

# Android: expose the mandatory assessment and the active-book rules.
a=ACT.read_text()
a=a.replace('APP_VERSION="3.9.0"','APP_VERSION="3.10.0"').replace('CLEAN STORY • REALTIME • V3.9','DISCIPLINED BOOK • REALTIME • V3.10')
a=a.replace('c.addView(line("MARKET STORY",s.optString("marketStory","BOT READS CURRENT STRUCTURE"),CYAN));', 'c.addView(line("MARKET STORY",s.optString("marketStory","BOT READS CURRENT STRUCTURE"),CYAN));JSONObject ea=s.optJSONObject("entryAssessment");if(ea!=null)c.addView(line("ENTRY ASSESSMENT",ea.optString("verdict","NO TRADE")+" • HARD STRUCTURE CHECKS",ea.optString("verdict","").equals("PASS")?GREEN:RED));')
a=a.replace('"LIVE REFRESH","500ms",', '"LIVE REFRESH","500ms • MAX 6 ACTIVE • 1/SYMBOL",')
ACT.write_text(a)

m=MON.read_text().replace('SignalHub V3.9 • CLEAN STORY LIVE','SignalHub V3.10 • DISCIPLINED BOOK LIVE')
MON.write_text(m)

api=API.read_text().replace('SignalHub-Android/3.9.0-clean-market-story','SignalHub-Android/3.10.0-disciplined-book')
API.write_text(api)

g=GRADLE.read_text().replace('versionCode 15','versionCode 16').replace("versionName '3.9.0'","versionName '3.10.0'")
GRADLE.write_text(g)

print('patched SignalHub V3.10 disciplined active book + mandatory entry assessment')
