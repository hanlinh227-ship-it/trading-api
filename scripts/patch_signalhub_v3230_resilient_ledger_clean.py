from pathlib import Path
import re

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
api=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
monitor=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
gradle=Path('signalhub-android/app/build.gradle')

w=worker.read_text(); a=activity.read_text(); c=api.read_text(); m=monitor.read_text(); g=gradle.read_text()

def block(text,start,end,replacement,name):
    i=text.find(start)
    assert i>=0, f'{name}: start marker missing'
    j=text.find(end,i)
    assert j>i, f'{name}: end marker missing'
    return text[:i]+replacement+text[j:]

def sub1(text,pattern,replacement,name,flags=0):
    out,n=re.subn(pattern,replacement,text,count=1,flags=flags)
    assert n==1, f'{name}: expected 1 replacement, got {n}'
    return out

# ---------------------------------------------------------------------------
# V3.23.0 identity and clean checkpoint. This is a consolidation release:
# older patches remain build inputs, but every live policy is overwritten here.
# ---------------------------------------------------------------------------
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.7','SIGNALHUB-V3-GATEWAY-3.23.0')
w=w.replace("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_20';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_30_RESILIENT_LEDGER';")
w=w.replace("versionCode: 36,","versionCode: 38,")
w=w.replace("versionName: '3.22.7'","versionName: '3.23.0'")
w=w.replace("title: 'SignalHub 3.22.7 Market-Only Health Seven'","title: 'SignalHub 3.23.0 Resilient Ledger Clean'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.7-Market-Only-Health-Seven'","artifactName: 'SignalHub-Android-v3.23.0-Resilient-Ledger-Clean'")
needle='  notes: [\n'
assert needle in w
w=w.replace(needle,needle+
"    'V3.23.0 is the consolidation release: it removes inherited 10/5 policy conflicts, keeps exactly 5 SCALP + 2 SWING active MARKET reference signals, and isolates runtime state in a fresh Durable Object namespace.',\n"
"    'V3.23.0 preserves generic analysis routing until final admission so legacy LIMIT/STOP analysis plans can be converted into a fresh MARKET geometry instead of being rejected prematurely. Active output remains MARKET-only.',\n"
"    'V3.23.0 makes signal history permanent: current signal rows and the dedicated history archive are written without expiration, legacy rows are migrated, and TP/SL win rate remains separate from AUTO_CUT outcomes.',\n"
"    'V3.23.0 hardens continuity with quote sequence numbers, provider retries, last-good quote preservation, WebSocket gap detection, REST reconciliation, exponential reconnect, and a disk-backed mobile quote cache.',\n",1)

# ---------------------------------------------------------------------------
# Canonical active-book policy. Fix the separate legacy global policy that was
# still 10 SCALP + 5 SWING even after the V3.22.7 nested policy was changed.
# ---------------------------------------------------------------------------
canonical_policy="""const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:7,maxActivePerMarket:7,maxActivePerStyle:5,maxNewPerScan:5,minActivePerMarket:7,minActivePerStyle:2,targetActivePerStyle:5,targetActiveByStyle:{SCALP:5,SWING:2},maxActiveByStyle:{SCALP:5,SWING:2},maxNewPerScanByStyle:{SCALP:5,SWING:2},maxActivePerRiskCluster:7,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_EXACT_5_SCALP_2_SWING_MARKET_ONLY',cryptoPendingMonitor:'DISABLED_MARKET_ONLY',cryptoHealthMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:0,replacementMode:'HEALTH_CUT_THEN_ASYNC_MARKET_RESCAN',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'TARGET_5_SCALP_2_SWING_MARKET_ONLY',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT',historyPersistence:'PERMANENT_NO_TTL_PLUS_ARCHIVE',transportContinuity:'WS_SEQUENCE_REST_RECONCILE_LAST_GOOD',forexDisabled:true});
"""
w=sub1(w,r"const PORTFOLIO_POLICY=Object\.freeze\(\{.*?\}\);\n",canonical_policy,'global PORTFOLIO_POLICY',re.S)
w=sub1(w,r"function styleTarget\(style\)\{.*?\}","function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?2:5;}",'styleTarget')

# Keep nested policy synchronized with the canonical one.
w=w.replace("performanceRetentionDays:365","performanceRetentionDays:null")
w=w.replace("historicalWinRateMode:'RESOLVED_TP_SL_PRIMARY_AUTO_CUT_SEPARATE'","historicalWinRateMode:'RESOLVED_TP_SL_PRIMARY_AUTO_CUT_SEPARATE_PERMANENT_HISTORY'")

# ---------------------------------------------------------------------------
# Generic analysis must NOT be converted to MARKET before analyzeCryptoCandidate
# has finished its context/cross-provider checks. This was the V3.22.7 starvation
# conflict. Only final marketOnlySevenCandidate/maybeCreate may force MARKET.
# ---------------------------------------------------------------------------
valid=r'''function validSignalStructure(signal){
  if(!signal)return false;
  const entry=Number(signal.entry||0),sl=Number(signal.sl||0),tp=Number(signal.tp3||signal.tp||0);
  if(!(entry>0&&sl>0&&tp>0&&Math.abs(entry-sl)>0))return false;
  const side=String(signal.side||'').toUpperCase(),dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  if(!dir)return false;
  if(dir>0&&!(sl<entry&&tp>entry))return false;
  if(dir<0&&!(sl>entry&&tp<entry))return false;
  return ['MARKET','LIMIT','STOP'].includes(String(signal.orderType||'MARKET').toUpperCase())||signal.watchReference===true||signal.studyOnly===true;
}
'''
w=block(w,'function validSignalStructure(signal){','function stampMarketJudgment(signal,market,style){',valid,'validSignalStructure')

stamp=r'''function stampMarketJudgment(signal,market,style){
  signal.decisionMode='BOT_MARKET_JUDGMENT';
  signal.admissionMode='ANALYZE_FIRST_FINAL_MARKET_ONLY_HARD_SAFETY';
  signal.market=String(market||signal.market||'CRYPTO').toUpperCase();
  signal.style=String(style||signal.style||'SCALP').toUpperCase();
  signal.styleProfile=STYLE_EXECUTION_POLICY[signal.style]||STYLE_EXECUTION_POLICY.SCALP;
  signal.manualTradeMonitoring=signal.studyOnly===true?false:true;
  signal.healthModel='V3230_REALTIME_SIGNAL_HEALTH_1S';
  signal.executionAction=signal.studyOnly===true?'REFERENCE_ONLY_NO_EXECUTION':'SIGNAL_ONLY_USER_MANUAL_EXECUTION';
  delete signal.score;delete signal.qualityGrade;delete signal.scoreMeaning;delete signal.admissionGate;
  delete signal.standbySource;
  return signal;
}

'''
w=block(w,'function stampMarketJudgment(signal,market,style){','export class MT5LiveState {',stamp,'stampMarketJudgment')

# ---------------------------------------------------------------------------
# Fresh DO namespace: stale 3.22.x registry/standby/policy state can never leak
# into this release. Historical rows remain in KV and are migrated separately.
# ---------------------------------------------------------------------------
w=w.replace("env.MT5_LIVE.idFromName('primary')","env.MT5_LIVE.idFromName('primary-v3230-resilient-ledger-clean')")

# ---------------------------------------------------------------------------
# Permanent history ledger. New signal rows have no expiration. Active pointer
# keys may expire; history/state rows do not. Dedicated archive is independent
# of version-specific active pointers and survives reconnect/redeploy.
# ---------------------------------------------------------------------------
history_block=r'''function historyStateKey(s){return `v323:history:${String(s.market||'CRYPTO').toUpperCase()}:${String(s.style||'SCALP').toUpperCase()}:${String(s.id||s.signalId||'')}`;}
function historyEventKey(s,event){
  const id=String(s.id||s.signalId||''),ts=String(s.closedAt||s.cancelledAt||s.triggeredAt||s.issuedAt||nowIso()).replace(/[^0-9TZ]/g,'');
  return `v323:event:${String(s.market||'CRYPTO').toUpperCase()}:${String(s.style||'SCALP').toUpperCase()}:${id}:${ts}:${String(event||s.outcome||s.status||'UPSERT').toUpperCase()}`;
}
async function persistHistoryState(env,s,event='UPSERT',writeEvent=false){
  if(!env?.SIGNALS_KV||!s)return;const id=String(s.id||s.signalId||'');if(!id)return;
  const clean={...s,id,signalId:id,historyPersistence:'PERMANENT_NO_TTL',historySchema:'V323_RESILIENT_LEDGER_1'};delete clean.kvKey;
  await env.SIGNALS_KV.put(historyStateKey(clean),JSON.stringify(clean));
  if(writeEvent){const evt={id,signalId:id,market:clean.market,style:clean.style,symbol:clean.symbol,status:clean.status,outcome:clean.outcome||null,resultR:clean.resultR??null,event:String(event||clean.outcome||clean.status||'UPSERT'),at:clean.closedAt||clean.cancelledAt||clean.triggeredAt||clean.issuedAt||nowIso(),engineVersion:clean.engineVersion||null,checkpoint:clean.checkpoint||null};await env.SIGNALS_KV.put(historyEventKey(clean,evt.event),JSON.stringify(evt));}
}
async function listRowsByPrefix(env,prefix,maxKeys=20000){
  if(!env?.SIGNALS_KV)return[];const keys=[];let cursor=undefined,pages=0;
  do{const page=await env.SIGNALS_KV.list({prefix,limit:1000,...(cursor?{cursor}:{})});keys.push(...(page.keys||[]));pages++;if(page.list_complete||!page.cursor||keys.length>=maxKeys)break;cursor=page.cursor;}while(pages<Math.ceil(maxKeys/1000));
  const out=[];for(let i=0;i<Math.min(keys.length,maxKeys);i+=50){const raws=await Promise.all(keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));for(const raw of raws){if(!raw)continue;try{out.push(JSON.parse(raw))}catch{}}}return out;
}
async function migratePermanentHistory(env,maxPerStyle=20000){
  const result={ok:true,schema:'V323_RESILIENT_LEDGER_1',migrated:0,styles:{}};
  for(const style of ['SCALP','SWING']){const rows=await listRowsByPrefix(env,v31Prefix('CRYPTO',style),maxPerStyle);let n=0;for(const s of rows){await persistHistoryState(env,s,'LEGACY_MIGRATION',false);n++;}result.styles[style]=n;result.migrated+=n;}return result;
}
async function writeV31Signal(env,s){
  const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s));
  const active=s.status==='PENDING'||s.status==='OPEN',styleKey=activePointer(s.market,s.style,s.symbol),anyKey=activeAnyPointer(s.market,s.symbol);
  if(active){await env.SIGNALS_KV.put(styleKey,s.id,{expirationTtl:SIGNAL_TTL});await env.SIGNALS_KV.put(anyKey,s.id,{expirationTtl:SIGNAL_TTL});}
  else{await env.SIGNALS_KV.delete(styleKey);const anyId=await env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===s.id)await env.SIGNALS_KV.delete(anyKey);}
  await persistHistoryState(env,s,active?'ACTIVE_UPSERT':(s.outcome||s.status||'RESOLVED'),!active);
  await syncRealtimeSignal(env,s,key);
}
'''
w=block(w,'async function writeV31Signal(env,s){','async function trackV31Signals',history_block+'async function trackV31Signals','writeV31Signal/permanent history')

# Direct Durable Object lifecycle writes bypass writeV31Signal, so make them
# permanent too and mirror every terminal/health transition into the archive.
w=w.replace("await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});","await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean));await persistHistoryState(this.env,clean,clean.outcome||clean.healthState||'LIFECYCLE',clean.status!=='OPEN');")
w=w.replace("await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL})","await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean));await persistHistoryState(this.env,clean,clean.outcome||clean.healthState||'LIFECYCLE',clean.status!=='OPEN')")

# ---------------------------------------------------------------------------
# History reads merge permanent archive + legacy v31 rows and dedupe by id.
# This prevents a version migration from making old outcomes disappear.
# ---------------------------------------------------------------------------
history_reader=r'''async function getV31HistorySignals(env,market,style,maxKeys=20000){
  if(!env?.SIGNALS_KV)return[];
  const legacy=await listRowsByPrefix(env,v31Prefix(market,style),maxKeys),archive=await listRowsByPrefix(env,`v323:history:${String(market).toUpperCase()}:${String(style).toUpperCase()}:`,maxKeys),by=new Map();
  const stamp=s=>Date.parse(s.closedAt||s.cancelledAt||s.lastCheckedAt||s.triggeredAt||s.issuedAt||0)||0;
  for(const s of [...legacy,...archive]){const id=String(s?.id||s?.signalId||'');if(!id)continue;const old=by.get(id);if(!old||stamp(s)>=stamp(old))by.set(id,s);}
  const out=[...by.values()];out.sort((a,b)=>(Date.parse(b.issuedAt||0)||0)-(Date.parse(a.issuedAt||0)||0));return out;
}
'''
w=block(w,'async function getV31HistorySignals(env,market,style,maxKeys=5000){','async function unifiedSignals',history_reader+'async function unifiedSignals','getV31HistorySignals')

# ---------------------------------------------------------------------------
# Fresh MARKET geometry from current price. Older LIMIT/STOP analysis is only
# used as structural context; active admission is still exactly MARKET.
# Recalculate cross-provider majority instead of treating any single opposing
# secondary venue as a blanket veto.
# ---------------------------------------------------------------------------
market_converter=r'''function marketOnlySevenCandidate(raw){
  const s={...(raw||{})},style=String(s.style||'SCALP').toUpperCase(),side=String(s.side||'').toUpperCase(),dir=['LONG','BUY'].includes(side)?1:['SHORT','SELL'].includes(side)?-1:0,read=s.marketReadV322||{},tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{},src=Number(s.sourcePrice||s.lastPrice||0),atr=Math.abs(Number(tech.atr||0));
  if(!dir||!(src>0&&atr>0))return null;
  const cross=s.crossProviderConsensus||{},checked=Number(cross.checked||0),confirmed=Number(cross.confirmed||0),opposed=Number(cross.opposed||0),crossQuality=checked===0?'UNAVAILABLE':confirmed>opposed?'CONFIRMED':opposed>confirmed?'OPPOSED':'MIXED';
  if(opposed>=2||(checked===1&&opposed===1))return null;
  const spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),move=Math.abs(Number(tech.change24hPct||0)),rsi=Number(tech.rsi||50),ext=Math.abs(Number(tech.extensionAtr||read.extensionAtr||0)),rule=stableUniverseRule(style);
  if(!(spread>=0&&spread<=rule.maxSpread&&turnover>=rule.minTurnover&&move<=rule.maxMove))return null;
  if((dir>0&&rsi>73)||(dir<0&&rsi<27))return null;
  const trends=Array.isArray(tech.tfTrend)?tech.tfTrend.map(x=>Number(x)>0?1:Number(x)<0?-1:0):[],derivedAligned=style==='SWING'?trends.length>=3&&trends[1]===dir&&trends[2]===dir:trends.length>=3&&trends[1]!==-dir&&trends[2]!==-dir&&(trends[1]===dir||trends[2]===dir),contextAligned=read.contextAligned===true||ev.v322ContextAligned===true||derivedAligned,contextStrong=read.contextStrong===true||(style==='SWING'&&derivedAligned),execEvent=read.executionEvent===true||Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),momentum=read.executionMomentum===true;
  if(style==='SWING'&&!contextStrong)return null;if(style==='SCALP'&&!contextAligned)return null;
  const maxExt=style==='SWING'?.34:.46;if(ext>maxExt)return null;
  const strict=read.marketEntryReady===true&&contextStrong&&execEvent&&momentum&&crossQuality==='CONFIRMED';
  const alignedSafe=contextAligned&&(momentum||execEvent||contextStrong)&&crossQuality!=='OPPOSED';if(!strict&&!alignedSafe)return null;
  const spreadPx=Math.max(0,src*spread/10000),minRisk=atr*(style==='SWING'?.95:.62),maxRisk=atr*(style==='SWING'?3.20:2.25),buffer=Math.max(atr*(style==='SWING'?.24:.18),spreadPx*3.0);
  const oldSl=Number(s.sl||0),inv=Number(s.invalidationLevel||0),recentLow=Number(tech.recentLow||0),recentHigh=Number(tech.recentHigh||0),ema50=Number(tech.ema50||0),candidates=dir>0?[inv,recentLow,oldSl,ema50].filter(x=>Number.isFinite(x)&&x>0&&x<src):[inv,recentHigh,oldSl,ema50].filter(x=>Number.isFinite(x)&&x>src);
  let anchor=candidates.length?(dir>0?Math.max(...candidates):Math.min(...candidates)):src-dir*minRisk,sl=anchor-dir*buffer,risk=Math.abs(src-sl);
  if(risk<minRisk){risk=minRisk;sl=src-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;
  const minRR=style==='SWING'?2.90:2.25,t1Base=src+dir*risk*1.00,t2Base=src+dir*risk*1.65,t3Base=src+dir*risk*minRR,oldT1=Number(s.tp1||0),oldT2=Number(s.tp2||0),oldT3=Number(s.tp3||s.tp||0);
  const useTarget=(old,base)=>dir>0?(old>src?Math.max(old,base):base):(old>0&&old<src?Math.min(old,base):base),tp1=useTarget(oldT1,t1Base),tp2=useTarget(oldT2,dir>0?Math.max(t2Base,tp1+risk*.25):Math.min(t2Base,tp1-risk*.25)),tp3=useTarget(oldT3,dir>0?Math.max(t3Base,tp2+risk*.35):Math.min(t3Base,tp2-risk*.35)),rr=Math.abs(tp3-src)/risk;
  if(rr<minRR)return null;
  return stampMarketJudgment({...s,orderType:'MARKET',status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',entry:Number(src.toPrecision(10)),actualEntry:Number(src.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),invalidationLevel:Number(anchor.toPrecision(10)),targetRR:Number(rr.toFixed(3)),coverageFallback:false,referenceFallback:false,marketOnly:true,marketOnlyQuality:strict?'STRICT_CONFIRMED':'ALIGNED_SAFE',marketOnlyFacts:{strict,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:momentum,crossProvider:crossQuality,crossChecked:checked,crossConfirmed:confirmed,crossOpposed:opposed,extensionAtr:Number(ext.toFixed(3)),spreadBps:spread,turnover24h:turnover,targetRR:Number(rr.toFixed(3)),riskAtr:Number((risk/atr).toFixed(3))},entryAssessment:{verdict:'PASS',method:'V3230_FRESH_MARKET_GEOMETRY_CONTEXT_LIQUIDITY_NO_WIN_PROBABILITY',failed:[]}},'CRYPTO',style);
}
function compareMarketOnlyQuality(a,b){
  const aq=a.marketOnlyQuality==='STRICT_CONFIRMED'?0:1,bq=b.marketOnlyQuality==='STRICT_CONFIRMED'?0:1;if(aq!==bq)return aq-bq;const af=a.marketOnlyFacts||{},bf=b.marketOnlyFacts||{};
  const cr=x=>x==='CONFIRMED'?0:x==='MIXED'?1:x==='UNAVAILABLE'?2:3,ac=cr(af.crossProvider),bc=cr(bf.crossProvider);if(ac!==bc)return ac-bc;
  for(const k of ['contextStrong','executionEvent','executionMomentum']){const av=af[k]?0:1,bv=bf[k]?0:1;if(av!==bv)return av-bv;}
  if(Number(af.spreadBps)!==Number(bf.spreadBps))return Number(af.spreadBps)-Number(bf.spreadBps);if(Number(af.extensionAtr)!==Number(bf.extensionAtr))return Number(af.extensionAtr)-Number(bf.extensionAtr);if(Number(af.riskAtr)!==Number(bf.riskAtr))return Number(af.riskAtr)-Number(bf.riskAtr);if(Number(af.turnover24h)!==Number(bf.turnover24h))return Number(bf.turnover24h)-Number(af.turnover24h);return Number(bf.targetRR||0)-Number(af.targetRR||0);
}

'''
w=block(w,'function marketOnlySevenCandidate(raw){','function setupPriority(s){',market_converter+'function setupPriority(s){','marketOnlySevenCandidate')

# Creation must force MARKET only after conversion and persist to permanent history.
maybe=r'''async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];style=String(style||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(marketOnlySevenCandidate).filter(Boolean).sort(compareMarketOnlyQuality),activeTotal=()=>book.length,styleCount=()=>book.filter(x=>String(x.style||'').toUpperCase()===style).length;
  for(const rawSetup of candidates){
    if(made.length>=styleNewLimit(style)||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||styleCount()>=styleTarget(style))break;
    const setup={...rawSetup,orderType:'MARKET',status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE'};if(!validSignalStructure(setup)||String(setup.orderType).toUpperCase()!=='MARKET')continue;if(book.some(x=>canonical(x.symbol)===canonical(setup.symbol)))continue;
    const issuedAt=nowIso(),id=`V3230M-CRYPTO-${style}-${canonical(setup.symbol)}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,6)}`,s=normalizeDisplaySignal({...setup,id,signalId:id,issuedAt,triggeredAt:issuedAt,actualEntry:Number(setup.entry),lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,portfolioPolicy:PORTFOLIO_POLICY,reservationMode:'DURABLE_OBJECT_ATOMIC_MARKET_ONLY',healthState:'HEALTHY',healthReason:'NEW_MARKET_SIGNAL',healthR:0,healthBestR:0,healthWorstR:0,healthAdverseTicks:0,healthWarningTicks:0,healthUpdatedAt:issuedAt,manualTradeMonitoring:true,executionAction:'SIGNAL_ONLY_USER_MANUAL_EXECUTION',historyPersistence:'PERMANENT_NO_TTL'},market,style),kvKey=v31Prefix(market,style)+id;
    const reservation=await reserveRealtimeSignal(env,s,kvKey);if(!reservation?.accepted)continue;s.portfolioReservation={accepted:true,mode:'DURABLE_OBJECT_ATOMIC_MARKET_ONLY',activeTotal:Number(reservation.activeTotal||0)};
    try{await writeV31Signal(env,s);await persistHistoryState(env,s,'CREATED',true);}catch(e){await releaseRealtimeSignal(env,id);throw e;}made.push(s);book.push(s);
  }
  return made;
}
'''
w=block(w,'async function maybeCreateV31(env,market,style,setups){','async function setCryptoStandbys',maybe+'async function setCryptoStandbys','maybeCreateV31')

# ---------------------------------------------------------------------------
# Provider continuity: retries, monotonic quote sequence, last-good quote carry
# for display only, and explicit freshness per quote. Stale fallback is never fed
# into TP/SL/AUTO_CUT evaluation.
# ---------------------------------------------------------------------------
cycle=r'''  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO'),previousStatus=(await this.state.storage.get('cryptoMonitorStatus'))||{},previousPack=(await this.state.storage.get('cryptoLiveQuotes'))||{},cycle=Number(previousStatus.cycle||0)+1,seq=Number(previousPack.seq||0)+1,at=nowIso();
    if(!active.length){const pack={type:'crypto_quotes',ok:true,seq,receivedAt:at,count:0,freshCount:0,staleCount:0,quotes:[],transportState:'IDLE_NO_ACTIVE'};await this.state.storage.put('cryptoLiveQuotes',pack);const status={ok:true,running:false,cycle,seq,activeCrypto:0,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast(pack);this.broadcast({type:'crypto_monitor',...status});return status;}
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[],freshBySymbol=new Map(),freshReceived=new Map();let quotes=0;
    for(const provider of providers){
      let snap=null,lastErr=null;for(let attempt=0;attempt<3;attempt++){try{const x=await cryptoSnapshotForProvider(this.env,provider);if(x?.live!==false&&x?.rows?.length){snap=x;break;}lastErr=new Error('NO_LIVE_ROWS');}catch(e){lastErr=e;}if(attempt<2)await sleep(120*(attempt+1));}
      if(!snap){errors.push(`${provider}:${String(lastErr?.message||'NO_LIVE_ROWS')}`);continue;}
      quotes+=snap.rows.length;const received=snap.receivedAt||at;freshReceived.set(provider,received);const by=new Map((snap.rows||[]).map(q=>[canonical(q.symbol),q]));for(const s of active){const authority=String(s.executionPriceAuthority||s.provider||s.exchange||'BYBIT').toUpperCase();if(authority!==provider)continue;const q=by.get(canonical(s.symbol));if(q)freshBySymbol.set(`${provider}:${canonical(s.symbol)}`,q);}events.push(...await this.evaluate('CRYPTO',snap.rows,received));
    }
    const oldById=new Map((previousPack.quotes||[]).map(q=>[String(q.signalId||''),q])),liveQuotes=[],now=Date.now();
    for(const s of active){const id=String(s.signalId||s.id||''),symbol=canonical(s.symbol),provider=String(s.executionPriceAuthority||s.provider||s.exchange||'BYBIT').toUpperCase(),q=freshBySymbol.get(`${provider}:${symbol}`);if(q){const received=freshReceived.get(provider)||at;liveQuotes.push({signalId:id,symbol,style:String(s.style||'').toUpperCase(),provider,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),receivedAt:received,stale:false,sourceState:'FRESH'});}else{const old=oldById.get(id),oldAt=Date.parse(old?.receivedAt||'');const age=Number.isFinite(oldAt)?now-oldAt:Infinity;if(old&&Number(old.lastPrice)>0&&age<=15000)liveQuotes.push({...old,stale:true,sourceState:'LAST_GOOD',quoteAgeMs:age});}}
    const freshCount=liveQuotes.filter(x=>!x.stale).length,staleCount=liveQuotes.length-freshCount,pack={type:'crypto_quotes',ok:freshCount>0,seq,receivedAt:at,count:liveQuotes.length,freshCount,staleCount,complete:liveQuotes.length===active.length,quotes:liveQuotes,providers,errors,transportState:staleCount?'DEGRADED_LAST_GOOD':'LIVE'};await this.state.storage.put('cryptoLiveQuotes',pack);this.broadcast(pack);
    const activeNow=this.activeRows(await this.registry()),underfilledStyles=['SWING','SCALP'].filter(st=>activeNow.filter(x=>String(x.style||'').toUpperCase()===st).length<styleTarget(st)),terminal=events.filter(e=>['CANCELLED','TP','SL','AUTO_CUT'].includes(String(e?.type||'')));if(underfilledStyles.length||terminal.length)this.broadcast({type:'book_refill_needed',styles:underfilledStyles.length?underfilledStyles:[...new Set(terminal.map(e=>String(e?.signal?.style||'').toUpperCase()).filter(Boolean))],receivedAt:at});
    const status={ok:errors.length<providers.length,running:true,cycle,seq,activeCrypto:activeNow.length,providers,quotes,liveSignalQuotes:liveQuotes.length,freshSignalQuotes:freshCount,staleSignalQuotes:staleCount,underfilledStyles,events:events.length,errors,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;
  }
'''
w=block(w,'  async cryptoMonitorCycle(){','  async alarm(){',cycle+'  async alarm(){','cryptoMonitorCycle')

# Retry live market snapshots before declaring transient provider failure.
scan=r'''async function loadCryptoSnapshotResilient(env){let last=null;for(let i=0;i<3;i++){try{last=await loadCryptoSnapshot(env);if(last?.live!==false&&Array.isArray(last?.rows)&&last.rows.length)return last;}catch(e){last={live:false,provider:'UNAVAILABLE',rows:[],error:String(e?.message||e)}}if(i<2)await sleep(250*(i+1));}return last||{live:false,provider:'UNAVAILABLE',rows:[]};}
async function scanCrypto(env,style){
  style=String(style||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const trackerEvents=await retireAllLegacyActiveSignals(env),snap=await loadCryptoSnapshotResilient(env);if(snap.live===false||!snap.rows?.length)return {ok:true,version:V3_VERSION,market:'CRYPTO',style,status:'NO_FRESH_CRYPTO_SNAPSHOT',retryable:true,created:0,provider:snap.provider,live:false,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};
  const all=snap.rows,stable100=await persistStable100(env,snap,all),portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style),liquid=stable100.filter(x=>stableUniverseEligible(x,style)),rankedLimit=styleUnderfilled?Math.min(100,liquid.length):(style==='SCALP'?Math.min(55,liquid.length):Math.min(48,liquid.length)),ranked=rotatingStableCandidates(liquid,style,rankedLimit),rawAnalyses=await analyzeCryptoBatch(ranked,style,7),marketCandidates=rawAnalyses.map(marketOnlySevenCandidate).filter(Boolean).sort(compareMarketOnlyQuality),created=await maybeCreateV31(env,'CRYPTO',style,marketCandidates),after=await realtimePortfolioSnapshot(env);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_RESILIENT_LEDGER',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:marketCandidates.length,strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='STRICT_CONFIRMED').length,safeFill:marketCandidates.filter(x=>x.marketOnlyQuality==='ALIGNED_SAFE').length,created:created.length,newSignals:created,activeAfter:after.styles?.[style]||0,targetActive:styleTarget(style),marketOnly:true,standby:{disabled:true,count:0},trackerEvents,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.23.0 final admission is MARKET-only 5 SCALP + 2 SWING. Generic pending/reference analysis is retained only as structural context, then a fresh current-price MARKET geometry is rebuilt with hard liquidity, context, extension, invalidation and target-path checks.'};
}

'''
w=block(w,'async function scanCrypto(env,style){','async function cryptoOnlyMaintenance(env){',scan+'async function cryptoOnlyMaintenance(env){','scanCrypto')

# Expose explicit history migration/diagnostic route and advertise continuity.
route_marker="if(url.pathname==='/v3/crypto/live-active'&&req.method==='GET'){const pack=await cryptoLiveSnapshot(env);return json({ok:pack.ok!==false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',...pack});}"
assert route_marker in w, 'live-active route marker missing'
w=w.replace(route_marker,route_marker+"\n    if(url.pathname==='/v3/history/migrate'&&req.method==='POST')return json({version:V3_VERSION,...await migratePermanentHistory(env)});",1)

# Performance/stability now report permanent retention instead of a misleading
# 365-day promise. The strict TP/SL denominator remains unchanged.
w=w.replace('retentionDays:365','retentionDays:null')
w=w.replace("policy:'TP_SL_WR_STRICT; AUTO_CUT_SEPARATE; ALL_EXIT_WR_INCLUDES_AUTO_CUT'","policy:'TP_SL_WR_STRICT; AUTO_CUT_SEPARATE; ALL_EXIT_WR_INCLUDES_AUTO_CUT; HISTORY_PERMANENT_NO_TTL'")
w=w.replace("mode:'CRYPTO_MARKET_ONLY_HEALTH'","mode:'CRYPTO_MARKET_ONLY_RESILIENT_LEDGER'")
w=w.replace("note:'Win rates are descriptive historical outcomes, never predicted probabilities. Strict TP/SL WR is kept separate from AUTO_CUT outcomes.'","note:'Win rates are descriptive historical outcomes, never predicted probabilities. Strict TP/SL WR is kept separate from AUTO_CUT outcomes. History is stored without expiration in the V3.23 resilient ledger.'")

# ---------------------------------------------------------------------------
# Android API transport: replace the inherited client wholesale to remove old
# UA/version remnants and add bounded retries/backoff.
# ---------------------------------------------------------------------------
c='''package com.hanlinh.signalhub;\n\nimport java.io.IOException;\nimport java.util.concurrent.ThreadLocalRandom;\nimport java.util.concurrent.TimeUnit;\n\nimport okhttp3.ConnectionPool;\nimport okhttp3.OkHttpClient;\nimport okhttp3.Request;\nimport okhttp3.Response;\nimport okhttp3.ResponseBody;\nimport okhttp3.WebSocket;\nimport okhttp3.WebSocketListener;\n\npublic final class ApiClient {\n    public static final String BASE_URL = "https://signalhub-forex.hanlinh227.workers.dev";\n    private static final String UA="SignalHub-Android/3.23.0";\n    private static final ConnectionPool POOL = new ConnectionPool(12, 5, TimeUnit.MINUTES);\n    private static final OkHttpClient API_CLIENT = new OkHttpClient.Builder().connectionPool(POOL).connectTimeout(5,TimeUnit.SECONDS).readTimeout(9,TimeUnit.SECONDS).callTimeout(14,TimeUnit.SECONDS).retryOnConnectionFailure(true).build();\n    private static final OkHttpClient LIVE_CLIENT = new OkHttpClient.Builder().connectionPool(POOL).connectTimeout(4,TimeUnit.SECONDS).readTimeout(7,TimeUnit.SECONDS).callTimeout(10,TimeUnit.SECONDS).pingInterval(5,TimeUnit.SECONDS).retryOnConnectionFailure(true).build();\n    private ApiClient() {}\n\n    public static WebSocket connectCryptoStream(WebSocketListener listener) {\n        String ws=BASE_URL.replace("https://","wss://").replace("http://","ws://")+"/v3/crypto/stream";\n        Request r=new Request.Builder().url(ws).header("Cache-Control","no-cache, no-store").header("Pragma","no-cache").header("User-Agent",UA).build();\n        return LIVE_CLIENT.newWebSocket(r,listener);\n    }\n    /** Compile compatibility only. Crypto-only UI does not open this stream. */\n    public static WebSocket connectForexStream(WebSocketListener listener) {\n        String ws=BASE_URL.replace("https://","wss://").replace("http://","ws://")+"/v3/forex/stream";\n        Request r=new Request.Builder().url(ws).header("Cache-Control","no-cache, no-store").header("User-Agent",UA).build();\n        return LIVE_CLIENT.newWebSocket(r,listener);\n    }\n    public static String get(String path) throws Exception {return getInternal(path,false);}\n    public static String getLive(String path) throws Exception {return getInternal(path,true);}\n    private static String getInternal(String path,boolean live) throws Exception {\n        String url=path.startsWith("http")?path:BASE_URL+path;OkHttpClient client=live?LIVE_CLIENT:API_CLIENT;IOException last=null;int attempts=4;\n        for(int attempt=0;attempt<attempts;attempt++){\n            Request req=new Request.Builder().url(url).get().header("Accept","application/json").header("Cache-Control","no-cache, no-store").header("Pragma","no-cache").header("User-Agent",UA).build();\n            try(Response resp=client.newCall(req).execute()){\n                ResponseBody body=resp.body();String text=body==null?"":body.string();\n                if(resp.isSuccessful())return text;\n                if(resp.code()<500&&resp.code()!=408&&resp.code()!=429)throw new IOException("HTTP "+resp.code()+" "+text);\n                last=new IOException("HTTP "+resp.code()+" "+text);\n            }catch(IOException e){last=e;}\n            if(attempt<attempts-1){long delay=Math.min(1400L,150L*(1L<<attempt))+ThreadLocalRandom.current().nextLong(40L,180L);try{Thread.sleep(delay);}catch(InterruptedException ie){Thread.currentThread().interrupt();throw new IOException("interrupted",ie);}}\n        }\n        throw last==null?new IOException("request failed"):last;\n    }\n}\n'''

# Android activity identity + disk-backed quote cache + sequence-aware reconnect.
a=a.replace('APP_VERSION="3.22.7"','APP_VERSION="3.23.0"')
a=a.replace('private volatile long fxStreamLastMs=0,cryptoStreamLastMs=0,lastCryptoStreamConnectAttemptMs=0,cryptoUniverseLastMs=0,watchLastBulkMs=0,watchLastRenderMs=0;',
'''private volatile long fxStreamLastMs=0,cryptoStreamLastMs=0,lastCryptoStreamConnectAttemptMs=0,cryptoUniverseLastMs=0,watchLastBulkMs=0,watchLastRenderMs=0,cryptoStreamSeq=0,cryptoReconnectBackoffMs=750;''')
a=a.replace('buildUi();ensureMonitor(true);renderCurrent(true);','buildUi();loadPersistedCryptoQuotes();ensureMonitor(true);renderCurrent(true);')

stream_methods=r'''    private void ensureCryptoStream(){
        long now=System.currentTimeMillis();if(cryptoSocket!=null&&cryptoStreamLastMs>0&&now-cryptoStreamLastMs<=4500)return;if(now-lastCryptoStreamConnectAttemptMs<cryptoReconnectBackoffMs)return;lastCryptoStreamConnectAttemptMs=now;
        try{if(cryptoSocket!=null)cryptoSocket.cancel();}catch(Throwable ignored){}cryptoSocket=null;
        try{cryptoSocket=ApiClient.connectCryptoStream(new WebSocketListener(){
            @Override public void onOpen(WebSocket webSocket,Response response){cryptoStreamLastMs=System.currentTimeMillis();cryptoReconnectBackoffMs=750;lastApiOkMs=cryptoStreamLastMs;main.post(()->updateConnectionViews());}
            @Override public void onMessage(WebSocket webSocket,String text){consumeCryptoStream(text);}
            @Override public void onFailure(WebSocket webSocket,Throwable t,Response response){if(cryptoSocket==webSocket)cryptoSocket=null;cryptoStreamLastMs=0;cryptoReconnectBackoffMs=Math.min(15000,Math.max(750,cryptoReconnectBackoffMs*2));scheduleCryptoReconnect();main.post(()->updateConnectionViews());}
            @Override public void onClosed(WebSocket webSocket,int code,String reason){if(cryptoSocket==webSocket)cryptoSocket=null;cryptoStreamLastMs=0;cryptoReconnectBackoffMs=Math.min(15000,Math.max(750,cryptoReconnectBackoffMs*2));scheduleCryptoReconnect();main.post(()->updateConnectionViews());}
        });}catch(Throwable ignored){cryptoSocket=null;cryptoStreamLastMs=0;cryptoReconnectBackoffMs=Math.min(15000,Math.max(750,cryptoReconnectBackoffMs*2));scheduleCryptoReconnect();}
    }
    private void scheduleCryptoReconnect(){long jitter=(long)(Math.random()*350);main.postDelayed(()->{if(resumed)ensureCryptoStream();},cryptoReconnectBackoffMs+jitter);}
    private void closeCryptoStream(){try{if(cryptoSocket!=null)cryptoSocket.close(1000,"activity-destroy");}catch(Throwable ignored){}cryptoSocket=null;}
    private void persistCryptoQuoteCache(){try{JSONObject root=new JSONObject();long now=System.currentTimeMillis();for(Map.Entry<String,Double> e:cryptoSignalPrices.entrySet()){Long at=cryptoSignalPriceAt.get(e.getKey());if(at==null||e.getValue()==null||e.getValue()<=0)continue;JSONObject x=new JSONObject();x.put("p",e.getValue());x.put("t",at);root.put(e.getKey(),x);}getSharedPreferences("signalhub_resilient_cache",MODE_PRIVATE).edit().putString("crypto_quotes_v323",root.toString()).putLong("saved_at_v323",now).apply();}catch(Throwable ignored){}}
    private void loadPersistedCryptoQuotes(){try{SharedPreferences p=getSharedPreferences("signalhub_resilient_cache",MODE_PRIVATE);JSONObject root=new JSONObject(p.getString("crypto_quotes_v323","{}"));long now=System.currentTimeMillis();for(java.util.Iterator<String> it=root.keys();it.hasNext();){String id=it.next();JSONObject x=root.optJSONObject(id);if(x==null)continue;double px=x.optDouble("p",0);long at=x.optLong("t",0);if(px>0&&at>0&&now-at<24L*60L*60L*1000L){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,at);}}if(!cryptoSignalPrices.isEmpty()){cryptoState="STALE";cryptoLastOkMs=p.getLong("saved_at_v323",0);}}catch(Throwable ignored){}}
    private void consumeCryptoStream(String text){
        try{JSONObject p=new JSONObject(text);String type=p.optString("type","");
            if("signal_event".equals(type)){JSONObject sig=p.optJSONObject("signal");String ev=p.optString("event","");if(sig!=null)applyRealtimeSignal(sig);if(ev.equals("AUTO_CUT")||ev.equals("TP")||ev.equals("SL")||ev.equals("CANCELLED"))io.execute(()->{try{ApiClient.get("/v3/status?appRefill="+System.currentTimeMillis());}catch(Throwable ignored){}});return;}
            if("book_refill_needed".equals(type)){io.execute(()->{try{ApiClient.get("/v3/status?wsRefill="+System.currentTimeMillis());}catch(Throwable ignored){}});return;}if(!"crypto_quotes".equals(type))return;
            long seq=p.optLong("seq",0),now=System.currentTimeMillis();boolean gap=cryptoStreamSeq>0&&seq>cryptoStreamSeq+1;if(seq>0)cryptoStreamSeq=seq;JSONArray q=p.optJSONArray("quotes");if(q==null)return;boolean stale=false;
            for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);long received=parseMs(x.optString("receivedAt",p.optString("receivedAt","")));if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:now);}if(x.optBoolean("stale",false))stale=true;}
            cryptoStreamLastMs=now;cryptoLastOkMs=now;lastApiOkMs=now;cryptoState=stale?"DELAYED":"LIVE";persistCryptoQuoteCache();if(gap)io.execute(this::reconcileCryptoLiveNow);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("HOME"))renderHome(false);});
        }catch(Throwable ignored){}
    }
    private void reconcileCryptoLiveNow(){try{JSONObject live=new JSONObject(ApiClient.getLive("/v3/crypto/live-active?reconcile="+System.currentTimeMillis()));long seq=live.optLong("seq",0);if(seq>cryptoStreamSeq)cryptoStreamSeq=seq;JSONArray q=live.optJSONArray("quotes");long now=System.currentTimeMillis();if(q!=null)for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);long received=parseMs(x.optString("receivedAt",live.optString("receivedAt","")));if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:now);}}if(q!=null&&q.length()>0){cryptoLastOkMs=now;lastApiOkMs=now;cryptoState=live.optInt("staleCount",0)>0?"DELAYED":"LIVE";persistCryptoQuoteCache();}}catch(Throwable ignored){}
    }

'''
a=block(a,'    private void ensureCryptoStream(){','    private void connectForexStream(){',stream_methods+'    private void connectForexStream(){','android crypto stream resilience')

refresh=r'''    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{boolean activeOk=false;try{
        JSONObject live=new JSONObject(ApiClient.getLive("/v3/crypto/live-active?mobile="+System.currentTimeMillis()));JSONArray q=live.optJSONArray("quotes");long seq=live.optLong("seq",0),now=System.currentTimeMillis();if(seq>cryptoStreamSeq)cryptoStreamSeq=seq;if(q!=null&&q.length()>0){boolean stale=false;for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);long received=parseMs(x.optString("receivedAt",live.optString("receivedAt","")));if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:now);}if(x.optBoolean("stale",false))stale=true;}activeOk=true;cryptoLastOkMs=now;lastApiOkMs=now;cryptoState=stale?"DELAYED":"LIVE";persistCryptoQuoteCache();}
        if(screen.equals("WATCH")||cryptoPrices.isEmpty()||now-cryptoUniverseLastMs>5000){try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000&mobile="+now));JSONArray arr=p.optJSONArray("tickers");Map<String,JSONObject> next=new ConcurrentHashMap<>();if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject z=arr.optJSONObject(i);if(z!=null&&z.optDouble("lastPrice",0)>0)next.put(z.optString("symbol",""),z);}if(!next.isEmpty()){cryptoPrices.clear();cryptoPrices.putAll(next);cryptoUniverseLastMs=now;}cryptoProvider=p.optString("provider",cryptoProvider);cryptoCount=p.optInt("count",next.size());}catch(Throwable ignored){}}
    }catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;if(!activeOk)cryptoState=age<6000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("WATCH"))updateWatchUniversePrices();});}});}

'''
a=block(a,'    private void refreshCryptoLive(){','    private void updateConnectionViews(){',refresh+'    private void updateConnectionViews(){','android refreshCryptoLive')
a=a.replace('SignalHub V3.22.7','SignalHub V3.23.0').replace('SignalHub 3.22.7','SignalHub 3.23.0')

# MonitorService: keep its existing behavior but remove old version labels and
# make alert history much less lossy (500 entries, apply MARKET-only 5/2 labels).
m=m.replace('SignalHub V3.22.7','SignalHub V3.23.0').replace('SignalHub V3.14','SignalHub V3.23.0')
m=m.replace('for(int i=0;i<old.length()&&i<49;i++)out.put(old.opt(i));','for(int i=0;i<old.length()&&i<499;i++)out.put(old.opt(i));')
m=m.replace('alert_history_v33','alert_history_v3230')
m=m.replace(' / 15 active',' / 7 active').replace('10 SCALP + 5 SWING','5 SCALP + 2 SWING')

g=g.replace('versionCode 36','versionCode 38').replace("versionName '3.22.7'","versionName '3.23.0'")

worker.write_text(w);activity.write_text(a);api.write_text(c);monitor.write_text(m);gradle.write_text(g)

# Hard source invariants. These catch inherited-version conflicts before deploy.
assert 'SIGNALHUB-V3-GATEWAY-3.23.0' in w
assert "SIGNALHUB_V3_CHECKPOINT_30_RESILIENT_LEDGER" in w
assert "targetActiveByStyle:{SCALP:5,SWING:2}" in w
assert w.count('const PORTFOLIO_POLICY=Object.freeze(')==1
assert "function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?2:5;}" in w
assert "primary-v3230-resilient-ledger-clean" in w
assert 'PERMANENT_NO_TTL' in w and 'migratePermanentHistory' in w
assert 'V3230_FRESH_MARKET_GEOMETRY_CONTEXT_LIQUIDITY_NO_WIN_PROBABILITY' in w
assert "orderType:'MARKET'" in w and 'V3230M-CRYPTO-' in w
assert 'loadCryptoSnapshotResilient' in w and 'seq' in w and 'LAST_GOOD' in w
assert 'APP_VERSION="3.23.0"' in a and 'cryptoStreamSeq' in a and 'cryptoReconnectBackoffMs' in a
assert 'crypto_quotes_v323' in a and 'reconcileCryptoLiveNow' in a
assert 'SignalHub-Android/3.23.0' in c and 'attempts=4' in c
assert 'SignalHub V3.23.0' in m and 'alert_history_v3230' in m
assert 'versionCode 38' in g and "versionName '3.23.0'" in g
# Disallow the specific stale live-policy contract that broke V3.22.7.
assert "coverageMode:'CRYPTO_EXACT_10_SCALP_5_SWING_STABLE_LIQUID_UNIVERSE'" not in w
print('patched SignalHub V3.23.0 resilient ledger clean')
