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
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.10.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.11.0';")
w=w.replace("versionCode: 16,\n  versionName: '3.10.0',\n  title: 'SignalHub 3.10.0',","versionCode: 17,\n  versionName: '3.11.0',\n  title: 'SignalHub 3.11.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.10.0',","artifactName: 'SignalHub-Android-v3.11.0',")
w=w.replace("    'V3.10 Disciplined Book keeps the clean market story model and adds portfolio-level concurrency discipline plus a mandatory hard-check assessment for every order.',","    'V3.11 Atomic Quality Book reserves every active slot transactionally inside one Durable Object so concurrent scans cannot overbook the portfolio.',\n    'V3.11 also caps Forex currency concentration at two active ideas per currency and tightens market-entry location / pending-trigger reachability checks.',\n    'V3.10 Disciplined Book keeps the clean market story model and adds portfolio-level concurrency discipline plus a mandatory hard-check assessment for every order.',")
w=w.replace("portfolioPolicy:{maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,oneActivePerSymbolAcrossStyles:true}","portfolioPolicy:{maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC'}")

new_register=r'''  async registerSignal(payload){
    const s=payload?.signal||payload,id=String(s?.id||s?.signalId||'');if(!id)return {ok:false,accepted:false,error:'NO_SIGNAL_ID'};
    const result=await this.state.storage.transaction(async txn=>{
      const reg=(await txn.get('signalRegistry'))||{},activeStatus=s.status==='PENDING'||s.status==='OPEN';
      if(!activeStatus){delete reg[id];await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:s.status,removed:true,reg};}
      const kvKey=String(payload?.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),existing=reg[id];
      if(existing){reg[id]={...s,kvKey};await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:s.status,idempotent:true,reg};}
      const active=Object.values(reg).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN'));
      const market=String(s.market||'').toUpperCase(),style=String(s.style||'').toUpperCase(),symbol=canonical(s.symbol),policy=PORTFOLIO_POLICY;
      const reject=reason=>({ok:true,accepted:false,id,status:s.status,reason,activeTotal:active.length,reg});
      const duplicate=active.find(x=>String(x.market||'').toUpperCase()===market&&canonical(x.symbol)===symbol);
      if(duplicate)return reject(`SYMBOL_ALREADY_ACTIVE:${duplicate.id||duplicate.symbol}`);
      if(active.length>=policy.maxActiveTotal)return reject('MAX_ACTIVE_TOTAL');
      if(active.filter(x=>String(x.market||'').toUpperCase()===market).length>=policy.maxActivePerMarket)return reject('MAX_ACTIVE_MARKET');
      if(active.filter(x=>String(x.style||'').toUpperCase()===style).length>=policy.maxActivePerStyle)return reject('MAX_ACTIVE_STYLE');
      if(market==='FOREX'&&symbol.length===6){
        const ccys=[symbol.slice(0,3),symbol.slice(3,6)];
        for(const ccy of ccys){
          const exposure=active.filter(x=>String(x.market||'').toUpperCase()==='FOREX').filter(x=>{const z=canonical(x.symbol);return z.length===6&&(z.slice(0,3)===ccy||z.slice(3,6)===ccy);}).length;
          if(exposure>=policy.maxForexPerCurrency)return reject(`MAX_FOREX_CURRENCY:${ccy}`);
        }
      }
      reg[id]={...s,kvKey};await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:s.status,activeTotal:active.length+1,reg};
    });
    this.signalRegistry=result.reg||this.signalRegistry;delete result.reg;return result;
  }'''
w=sub1(w,r"  async registerSignal\(payload\)\{.*?\n  \}\n  async unregisterSignal",new_register+"\n  async unregisterSignal",'atomic DO register')

# Keep unregister transactional too, avoiding a stale in-memory registry overwriting a concurrent reservation.
new_unregister=r'''  async unregisterSignal(payload){
    const id=String(payload?.id||payload?.signalId||'');if(!id)return {ok:false};
    let next={};await this.state.storage.transaction(async txn=>{const reg=(await txn.get('signalRegistry'))||{};delete reg[id];await txn.put('signalRegistry',reg);next=reg;});this.signalRegistry=next;return {ok:true,id};
  }'''
w=sub1(w,r"  async unregisterSignal\(payload\)\{.*?\}\n  async evaluate",new_unregister+"\n  async evaluate",'transactional unregister')

# Strengthen the portfolio policy and assessment without introducing a numeric score gate.
w=w.replace("const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,oneActivePerSymbolAcrossStyles:true});","const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC'});")

new_assess=r'''function assessEntrySetup(raw){
  const s=raw||{},dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
  const entry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp),src=Number(s.sourcePrice||s.lastPrice||0),inv=Number(s.invalidationLevel),tech=s.technicalAtIssue||{};
  const order=String(s.orderType||'').toUpperCase(),regime=String(s.marketRegime||''),expectedStyle=s.style==='SWING'?'SWING_HTF_STRUCTURE':'SCALP_MICROSTRUCTURE';
  const levels=dir>0?sl<entry&&entry<t1&&t1<t2&&t2<t3:sl>entry&&entry>t1&&t1>t2&&t2>t3;
  const contextSeries=Array.isArray(tech.tfTrend)?tech.tfTrend:Array.isArray(tech.recommend)?tech.recommend:[];
  const contextTail=contextSeries.slice(1).map(signOf).filter(Boolean),contextAligned=contextTail.length>0&&contextTail.every(x=>x!==-dir);
  const ext=Math.abs(Number(tech.extensionAtr||0)),maxMarketExt=s.style==='SWING'?.24:.30,risk=Math.abs(entry-sl),triggerDistance=risk>0&&src>0?Math.abs(src-entry)/risk:999;
  const marketLocation=order==='MARKET'?(regime.includes('LIQUIDITY')||ext<=maxMarketExt):order==='LIMIT'?(dir>0?entry<src:entry>src):order==='STOP'?(dir>0?entry>src:entry<src):false;
  const pendingReachable=order==='MARKET'||(order==='LIMIT'?triggerDistance<=1.20:order==='STOP'?triggerDistance<=.75:false);
  const invalidation=Number.isFinite(inv)&&inv>0&&(dir>0?inv<entry:inv>entry);
  const rationale=Array.isArray(s.rationale)?s.rationale:[],wide=String(s.executionCaution||'NORMAL').toUpperCase()==='WIDE';
  const checks={
    cleanStory:typeof s.marketStory==='string'&&s.marketStory.trim().length>=18,
    styleModel:s.styleExecutionModel===expectedStyle,
    contextAligned,
    entryLocation:src>0&&marketLocation,
    pendingReachable,
    invalidation,
    targetPath:levels,
    executionModel:typeof s.entryModel==='string'&&s.entryModel.length>8&&typeof s.slModel==='string'&&s.slModel.length>8&&typeof s.tpModel==='string'&&s.tpModel.length>8,
    rationaleComplete:rationale.length>=4,
    executionConditions:!wide,
    liveSource:src>0
  };
  const failed=Object.entries(checks).filter(([,v])=>!v).map(([k])=>k),pass=failed.length===0;
  return {verdict:pass?'PASS':'NO_TRADE',method:'HARD_STRUCTURE_CHECKS_NO_NUMERIC_SCORE',checks,failed,geometry:{extensionAtr:Number(ext.toFixed(3)),triggerDistanceR:Number(triggerDistance.toFixed(3)),maxMarketExtensionAtr:maxMarketExt}};
}'''
w=sub1(w,r"function assessEntrySetup\(raw\)\{.*?\n\}\nfunction setupPriority",new_assess+"\nfunction setupPriority",'stricter assessment')

# Only current-generation entries occupy the preflight book; the Durable Object is still the atomic source of truth.
w=w.replace("for(const s of rows)if(s.status==='PENDING'||s.status==='OPEN')out.push(s);","for(const s of rows)if((s.status==='PENDING'||s.status==='OPEN')&&String(s.engineVersion||'')===V3_VERSION)out.push(s);")

# Add an all-partition migration before any fresh evaluation so legacy signals never consume new-generation slots.
needle="async function maybeCreateV31(env,market,style,setups){"
insert=r'''async function retireAllLegacyActiveSignals(env){
  const events=[];for(const m of ['FOREX','CRYPTO'])for(const s of ['SCALP','SWING'])events.push(...await retireLegacyActiveSignals(env,m,s));return events;
}
async function reserveRealtimeSignal(env,s,kvKey){
  const stub=mt5LiveStub(env);if(!stub)return {accepted:false,reason:'NO_ATOMIC_RESERVATION_BUS'};
  try{const r=await stub.fetch('https://mt5-live/register-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({signal:s,kvKey})});if(!r.ok)return {accepted:false,reason:`RESERVATION_HTTP_${r.status}`};return await r.json();}catch(e){return {accepted:false,reason:`RESERVATION_ERROR:${String(e?.message||e)}`};}
}
async function releaseRealtimeSignal(env,id){const stub=mt5LiveStub(env);if(!stub)return;try{await stub.fetch('https://mt5-live/unregister-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id})});}catch{}}
'''
if needle not in w: raise SystemExit('maybeCreate needle missing')
w=w.replace(needle,insert+needle,1)

new_create=r'''async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];
  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(x=>{const assessment=assessEntrySetup(x);return {...x,entryAssessment:assessment};}).filter(x=>x.entryAssessment.verdict==='PASS').sort(compareSetupPriority);
  const activeTotal=()=>book.length,marketCount=()=>book.filter(x=>x.market===market).length,styleCount=()=>book.filter(x=>x.style===style).length;
  for(const rawSetup of candidates){
    if(made.length>=PORTFOLIO_POLICY.maxNewPerScan||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||marketCount()>=PORTFOLIO_POLICY.maxActivePerMarket||styleCount()>=PORTFOLIO_POLICY.maxActivePerStyle)break;
    const setup=stampMarketJudgment({...rawSetup},market,style);if(!validSignalStructure(setup))continue;
    if(book.some(x=>x.market===market&&x.symbol===setup.symbol))continue;
    const issuedAt=nowIso(),id=`V311-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,portfolioPolicy:PORTFOLIO_POLICY,reservationMode:'DURABLE_OBJECT_ATOMIC'},market,style),kvKey=v31Prefix(market,style)+id;
    const reservation=await reserveRealtimeSignal(env,s,kvKey);if(!reservation?.accepted)continue;
    s.portfolioReservation={accepted:true,mode:'DURABLE_OBJECT_ATOMIC',activeTotal:Number(reservation.activeTotal||0)};
    try{await writeV31Signal(env,s);}catch(e){await releaseRealtimeSignal(env,id);throw e;}
    made.push(s);book.push(s);
  }
  return made;
}'''
w=sub1(w,r"async function maybeCreateV31\(env,market,style,setups\)\{.*?\n\}\nasync function scanCrypto",new_create+"\nasync function scanCrypto",'atomic maybeCreate')

# Move migration to the beginning of each scan. This is signal-feed cleanup only; it never sends a broker close.
old_crypto="async function scanCrypto(env,style){\n  const snap=await loadCryptoSnapshot(env),all=snap.rows;\n  const ranked=all.filter(x=>Number(x.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,style==='SCALP'?12:10);\n  const trackerEvents=await retireLegacyActiveSignals(env,'CRYPTO',style);"
new_crypto="async function scanCrypto(env,style){\n  const trackerEvents=await retireAllLegacyActiveSignals(env);\n  const snap=await loadCryptoSnapshot(env),all=snap.rows;\n  const ranked=all.filter(x=>Number(x.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,style==='SCALP'?12:10);"
if old_crypto not in w: raise SystemExit('crypto scan migration pattern missing')
w=w.replace(old_crypto,new_crypto,1)

old_fx="async function scanForexJudgment(env,style){\n  const ex=await exnessQuoteMap(env);if(ex.state==='OFFLINE'||ex.state==='STALE')return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'NO_CURRENT_EXNESS_QUOTE',created:0,state:ex.state,ageMs:ex.ageMs,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time gate is applied, but stale data is never treated as a current market price.'};\n  const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await retireLegacyActiveSignals(env,'FOREX',style),rawSetups="
new_fx="async function scanForexJudgment(env,style){\n  const trackerEvents=await retireAllLegacyActiveSignals(env);\n  const ex=await exnessQuoteMap(env);if(ex.state==='OFFLINE'||ex.state==='STALE')return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'NO_CURRENT_EXNESS_QUOTE',created:0,state:ex.state,ageMs:ex.ageMs,trackerEvents,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time gate is applied, but stale data is never treated as a current market price.'};\n  const rows=await tvForexFrames(style),priceMap=ex.map,rawSetups="
if old_fx not in w: raise SystemExit('forex scan migration pattern missing')
w=w.replace(old_fx,new_fx,1)

# Ensure API notes identify atomic reservation.
w=w.replace("Portfolio caps prevent duplicate and excessive simultaneous entries.","Atomic Durable Object reservation and portfolio caps prevent duplicate and excessive simultaneous entries.")
WORKER.write_text(w)

a=ACT.read_text().replace('APP_VERSION="3.10.0"','APP_VERSION="3.11.0"').replace('DISCIPLINED BOOK • REALTIME • V3.10','ATOMIC QUALITY BOOK • REALTIME • V3.11')
a=a.replace('"500ms • MAX 6 ACTIVE • 1/SYMBOL"','"500ms • MAX 6 ACTIVE • 1/SYMBOL • ATOMIC"')
ACT.write_text(a)

m=MON.read_text().replace('SignalHub V3.10 • DISCIPLINED BOOK LIVE','SignalHub V3.11 • ATOMIC QUALITY BOOK LIVE')
MON.write_text(m)

api=API.read_text().replace('SignalHub-Android/3.10.0-disciplined-book','SignalHub-Android/3.11.0-atomic-quality-book')
API.write_text(api)

g=GRADLE.read_text().replace('versionCode 16','versionCode 17').replace("versionName '3.10.0'","versionName '3.11.0'")
GRADLE.write_text(g)

print('patched SignalHub V3.11 atomic reservation + stricter quality assessment')
