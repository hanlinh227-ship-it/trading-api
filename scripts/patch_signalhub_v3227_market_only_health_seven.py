from pathlib import Path

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
    assert j>=0, f'{name}: end marker missing'
    return text[:i]+replacement+text[j:]

def once(text,old,new,name):
    assert old in text, f'{name}: marker missing'
    return text.replace(old,new,1)

# ---------------------------------------------------------------------------
# Identity / retention
# ---------------------------------------------------------------------------
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.6','SIGNALHUB-V3-GATEWAY-3.22.7')
w=w.replace("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_10';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_20';")
w=w.replace('const SIGNAL_TTL = 60 * 60 * 24 * 90;','const SIGNAL_TTL = 60 * 60 * 24 * 365;')
w=w.replace("versionCode: 30,","versionCode: 36,")
w=w.replace("versionName: '3.22.6'","versionName: '3.22.7'")
w=w.replace("title: 'SignalHub 3.22.6 Balanced Realtime Book'","title: 'SignalHub 3.22.7 Market-Only Health Seven'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.6-Balanced-Realtime-Book'","artifactName: 'SignalHub-Android-v3.22.7-Market-Only-Health-Seven'")
needle='  notes: [\n'
assert needle in w
w=w.replace(needle,needle+"    'V3.22.7 is MARKET-only: exactly 5 SCALP + 2 SWING active reference signals; LIMIT and STOP are disabled in generation, reservation, active reads and portfolio audits.',\n    'V3.22.7 ranks live entries by structure/context, execution momentum, anti-extension, liquidity/spread, target path and secondary-venue agreement. It never labels an internal ranking as win probability.',\n    'V3.22.7 adds a 1-second signal-health monitor with HEALTHY/WATCH/WARNING states and conservative AUTO_CUT signal retirement before replacement. AUTO_CUT is a signal-feed action only; a manually opened exchange position must still be closed by the user unless a broker execution connector is added.',\n    'V3.22.7 preserves one year of signal history. Strict TP/SL win rate remains separate from all-exit statistics so early AUTO_CUT decisions cannot inflate historical win rate.',\n",1)

# ---------------------------------------------------------------------------
# Market-only policy and style models
# ---------------------------------------------------------------------------
policy=r'''const MARKET_JUDGMENT_POLICY = Object.freeze({
  name:'CRYPTO_MARKET_ONLY_QUALITY_JUDGMENT',
  scoreGate:false,
  timeGate:false,
  rrGate:false,
  orderRouting:'MARKET_ONLY_TOP_5_SCALP_2_SWING',
  historicalWinRateMode:'RESOLVED_TP_SL_PRIMARY_AUTO_CUT_SEPARATE',
  performanceRetentionDays:365,
  entryModel:'STRUCTURE_LIQUIDITY_CONTEXT_MARKET_ONLY',
  stopModel:'INVALIDATION_STRUCTURE_PLUS_VOLATILITY_BUFFER',
  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION',
  styleSeparation:'SCALP_MICROSTRUCTURE_VS_SWING_HTF_STRUCTURE',
  pendingActivation:'DISABLED_MARKET_ONLY',
  qualityMode:'TOP_RANKED_MARKET_ONLY_WITH_HARD_SAFETY',
  lifecycleSource:'DURABLE_OBJECT_REALTIME_SINGLE_SOURCE',
  healthModel:'V3227_REALTIME_SIGNAL_HEALTH_1S',
  autoCutExecution:'SIGNAL_RETIRE_ONLY_NO_BROKER_EXECUTION',
  portfolioPolicy:{maxActiveTotal:7,maxActivePerMarket:7,maxActivePerStyle:5,maxNewPerScan:5,minActivePerMarket:7,minActivePerStyle:2,targetActivePerStyle:5,targetActiveByStyle:{SCALP:5,SWING:2},maxActiveByStyle:{SCALP:5,SWING:2},maxNewPerScanByStyle:{SCALP:5,SWING:2},maxActivePerRiskCluster:7,maxMemeActiveTotal:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'CRYPTO_EXACT_5_SCALP_2_SWING_MARKET_ONLY',cryptoPendingMonitor:'DISABLED_MARKET_ONLY',cryptoHealthMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:0,replacementMode:'HEALTH_CUT_THEN_ASYNC_MARKET_RESCAN',universeRefresh:'DYNAMIC_STABLE100_EVERY_SERVER_CYCLE_PLUS_ON_DEMAND',stableUniverseSize:100,stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC',deepScanRotation:'LIQUIDITY_CORE_PLUS_ROTATING_COVERAGE',continuousRefill:'TARGET_5_SCALP_2_SWING_MARKET_ONLY',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT',forexDisabled:true}
});

const MARKET_HEALTH_POLICY=Object.freeze({
  watchR:-0.30,warningR:-0.50,persistentCutR:-0.68,emergencyCutR:-0.86,
  adverseTicksForCut:5,warningTicksForCut:6,stressedCutR:-0.58,
  profitProtectStartR:1.15,profitGivebackR:0.80,
  minAgeBeforeCutMs:{SCALP:30000,SWING:120000},
  spreadStressMultiplier:2.20,liquidityStressRatio:0.60,
  action:'SIGNAL_RETIRE_ONLY_USER_CLOSES_MANUAL_POSITION'
});

'''
w=block(w,'const MARKET_JUDGMENT_POLICY = Object.freeze({','const STYLE_EXECUTION_POLICY = Object.freeze({',policy,'policy')

styles=r'''const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE_MARKET_ONLY',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'MARKET only; prefer fresh liquidity sweep/reclaim or confirmed displacement/breakout with M15/H1 support, clean momentum, tight spread and no extension chase',stopFocus:'micro swing/liquidity invalidation + ATR/spread buffer',targetFocus:'clean 15m/1h liquidity with at least 2.15R final geometry',holdModel:'short-horizon; realtime health warning before conservative signal retirement'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE_MARKET_ONLY',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'MARKET only; H4+D1 alignment mandatory, H1 rejoin/reclaim/breakout preferred, clean momentum and no extended entry',stopFocus:'H1/H4 invalidation outside liquidity + wider ATR buffer',targetFocus:'H4/D1 liquidity with at least 2.75R final geometry',holdModel:'multi-session; realtime health warning before conservative signal retirement'})
});

'''
w=block(w,'const STYLE_EXECUTION_POLICY = Object.freeze({','function validSignalStructure(signal){',styles,'style policy')

valid=r'''function validSignalStructure(signal){
  if(!signal)return false;
  const entry=Number(signal.entry||0),sl=Number(signal.sl||0),tp=Number(signal.tp3||signal.tp||0);
  if(!(entry>0&&sl>0&&tp>0&&Math.abs(entry-sl)>0))return false;
  const side=String(signal.side||'').toUpperCase(),dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  if(!dir)return false;
  if(dir>0&&!(sl<entry&&tp>entry))return false;
  if(dir<0&&!(sl>entry&&tp<entry))return false;
  return String(signal.orderType||'MARKET').toUpperCase()==='MARKET';
}
'''
w=block(w,'function validSignalStructure(signal){','function stampMarketJudgment(signal,market,style){',valid,'valid signal')

stamp=r'''function stampMarketJudgment(signal,market,style){
  signal.decisionMode='BOT_MARKET_JUDGMENT';
  signal.admissionMode='MARKET_ONLY_HARD_SAFETY_NO_WIN_PROBABILITY';
  signal.market=String(market||signal.market||'CRYPTO').toUpperCase();
  signal.style=String(style||signal.style||'SCALP').toUpperCase();
  signal.orderType='MARKET';signal.status='OPEN';signal.entryState='LIVE';signal.lifecycle='ACTIVE';
  signal.styleProfile=STYLE_EXECUTION_POLICY[signal.style]||STYLE_EXECUTION_POLICY.SCALP;
  signal.manualTradeMonitoring=true;signal.healthModel='V3227_REALTIME_SIGNAL_HEALTH_1S';
  signal.executionAction='SIGNAL_ONLY_USER_MANUAL_EXECUTION';
  delete signal.score;delete signal.qualityGrade;delete signal.scoreMeaning;delete signal.admissionGate;
  delete signal.coverageFallback;delete signal.coverageTier;delete signal.standbySource;
  return signal;
}

'''
w=block(w,'function stampMarketJudgment(signal,market,style){','export class MT5LiveState {',stamp,'stamp')

# Canonical targets.
w=w.replace("function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?5:10;}","function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?2:5;}")

# ---------------------------------------------------------------------------
# Durable Object active book: current-version OPEN MARKET rows only
# ---------------------------------------------------------------------------
w=once(w,"  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN')&&String(x.market||'').toUpperCase()==='CRYPTO');}","  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&x.status==='OPEN'&&String(x.market||'').toUpperCase()==='CRYPTO'&&String(x.engineVersion||'')===V3_VERSION&&String(x.orderType||'MARKET').toUpperCase()==='MARKET');}",'activeRows')

portfolio=r'''  portfolioFrom(reg){
    const active=this.activeRows(reg),counts={FOREX:0,CRYPTO:0},styles={SCALP:0,SWING:0},orderTypes={SCALP:{MARKET:0,LIMIT:0,STOP:0},SWING:{MARKET:0,LIMIT:0,STOP:0}},symbolCounts={};
    for(const s of active){const m=String(s.market||'').toUpperCase(),st=String(s.style||'').toUpperCase(),ot=String(s.orderType||'MARKET').toUpperCase(),sym=canonical(s.symbol);if(m in counts)counts[m]++;if(st in styles)styles[st]++;if(orderTypes[st]&&ot in orderTypes[st])orderTypes[st][ot]++;if(sym)symbolCounts[sym]=(symbolCounts[sym]||0)+1;}
    const duplicateSymbols=Object.entries(symbolCounts).filter(([,n])=>n>1).map(([symbol])=>symbol),uniqueSymbols=Object.keys(symbolCounts).length;
    const marketOnly=orderTypes.SCALP.LIMIT===0&&orderTypes.SCALP.STOP===0&&orderTypes.SWING.LIMIT===0&&orderTypes.SWING.STOP===0&&orderTypes.SCALP.MARKET===5&&orderTypes.SWING.MARKET===2;
    return {activeTotal:active.length,counts,styles,orderTypes,uniqueSymbols,duplicateSymbols,marketOnly,exactTarget:styles.SCALP===5&&styles.SWING===2&&active.length===7&&uniqueSymbols===7&&duplicateSymbols.length===0&&marketOnly,policy:PORTFOLIO_POLICY};
  }
'''
w=block(w,'  portfolioFrom(reg){','  async portfolioSnapshot(){',portfolio,'portfolioFrom')

register=r'''  async registerSignal(payload){
    const s=payload?.signal||payload,id=String(s?.id||s?.signalId||'');if(!id)return {ok:false,accepted:false,error:'NO_SIGNAL_ID'};
    const result=await this.state.storage.transaction(async txn=>{
      const reg=(await txn.get('signalRegistry'))||{},existing=reg[id];
      if(existing&&String(existing.engineVersion||'')===V3_VERSION){reg[id]={...s,id,signalId:id,engineVersion:V3_VERSION,orderType:'MARKET',status:'OPEN',kvKey:existing.kvKey||payload?.kvKey};await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:'OPEN',idempotent:true,reg};}
      const active=this.activeRows(reg),market=String(s.market||'').toUpperCase(),style=String(s.style||'').toUpperCase(),symbol=canonical(s.symbol),order=String(s.orderType||'MARKET').toUpperCase();
      const reject=reason=>({ok:true,accepted:false,id,status:s.status,reason,activeTotal:active.length,reg});
      if(market!=='CRYPTO')return reject('CRYPTO_ONLY_FOREX_DISABLED');
      if(!['SCALP','SWING'].includes(style))return reject('BAD_STYLE');
      if(order!=='MARKET'||String(s.status||'').toUpperCase()!=='OPEN')return reject('MARKET_ONLY_OPEN_REQUIRED');
      const duplicate=active.find(x=>canonical(x.symbol)===symbol);if(duplicate)return reject(`SYMBOL_ALREADY_ACTIVE:${duplicate.id||duplicate.symbol}`);
      if(active.length>=PORTFOLIO_POLICY.maxActiveTotal)return reject('MAX_ACTIVE_TOTAL');
      if(active.filter(x=>String(x.style||'').toUpperCase()===style).length>=styleTarget(style))return reject('MAX_ACTIVE_STYLE');
      const cluster=cryptoRiskCluster(symbol),clusterCount=active.filter(x=>cryptoRiskCluster(x.symbol)===cluster).length;if(cluster==='MEME'&&clusterCount>=PORTFOLIO_POLICY.maxMemeActiveTotal)return reject('MAX_MEME_CLUSTER');
      const kvKey=String(payload?.kvKey||`v31:signal:CRYPTO:${style}:${id}`),row={...s,id,signalId:id,market:'CRYPTO',style,symbol,orderType:'MARKET',status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',engineVersion:V3_VERSION,riskCluster:cluster,kvKey};
      reg[id]=row;await txn.put('signalRegistry',reg);return {ok:true,accepted:true,id,status:'OPEN',activeTotal:active.length+1,reg};
    });
    this.signalRegistry=result.reg||this.signalRegistry;delete result.reg;
    if(result.accepted)try{await this.ensureCryptoMonitor(25);}catch{}
    return result;
  }
'''
w=block(w,'  async registerSignal(payload){','  async unregisterSignal(payload){',register,'registerSignal')

# No pending standby or style migration is allowed in a MARKET-only book.
rebalance=r'''  async rebalanceForStyle(payload){return {ok:true,style:String(payload?.style||'').toUpperCase(),released:[],reason:'V3227_MARKET_ONLY_NO_PENDING_REBALANCE'};}
'''
w=block(w,'  async rebalanceForStyle(payload){','  async promoteStandby(style,reason=',rebalance,'rebalance')
promote=r'''  async promoteStandby(style,reason='AUTO_REPLACE'){return {ok:true,style:String(style||'').toUpperCase(),promoted:[],remaining:0,reason:'V3227_MARKET_ONLY_STANDBY_DISABLED'};}
'''
w=block(w,"  async promoteStandby(style,reason='AUTO_REPLACE'){",'  async evaluate(market,rows,receivedAt){',promote,'promote standby')

# ---------------------------------------------------------------------------
# 1-second health evaluator. It retires the SIGNAL only; it does not execute
# against a user's exchange account.
# ---------------------------------------------------------------------------
evaluate=r'''  async evaluate(market,rows,receivedAt){
    const reg=await this.registry(),by=new Map();
    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);const provider=String(q?.exchange||q?.provider||'').toUpperCase();if(provider)by.set(`${provider}:${sym}`,q);}
    const changed=[],at=receivedAt||nowIso();let dirty=false;
    for(const [id,s] of Object.entries(reg)){
      if(String(s.engineVersion||'')!==V3_VERSION)continue;
      if(String(s.market||'').toUpperCase()!==String(market||'').toUpperCase())continue;
      if(s.status!=='OPEN'||String(s.orderType||'MARKET').toUpperCase()!=='MARKET'){delete reg[id];dirty=true;continue;}
      const sym=canonical(s.symbol),authority=String(s.executionPriceAuthority||s.provider||s.exchange||'').toUpperCase(),q=authority?by.get(`${authority}:${sym}`):by.get(sym);if(!q)continue;
      const dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,last=Number(q.lastPrice||q.last||q.mid||0),bid=Number(q.bid||last||0),ask=Number(q.ask||last||0),exitPx=dir>0?bid:ask;if(!(exitPx>0))continue;
      const entry=Number(s.actualEntry||s.entry),sl=Number(s.sl),tp=Number(s.tp3||s.tp),risk=Math.abs(entry-sl);if(!(entry>0&&sl>0&&tp>0&&risk>0))continue;
      const hitTp=dir>0?exitPx>=tp:exitPx<=tp,hitSl=dir>0?exitPx<=sl:exitPx>=sl;
      if(hitTp||hitSl){
        const exit=hitTp?tp:sl;s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=exit;s.resultR=Number((dir*(exit-entry)/risk).toFixed(4));s.resolution='PROVIDER_BID_ASK_REALTIME_TRACKER';s.healthState=hitTp?'CLOSED_TP':'CLOSED_SL';s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);const anyKey=`v31:active:any:${clean.market}:${clean.symbol}`,anyId=await this.env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===clean.id)await this.env.SIGNALS_KV.delete(anyKey);}
        delete reg[id];dirty=true;const evt={type:s.outcome,signal:clean,price:exitPx,at};changed.push(evt);this.broadcast({type:'signal_event',event:s.outcome,signal:clean,price:exitPx,receivedAt:at});continue;
      }
      const r=dir*(exitPx-entry)/risk,prev=Number(s.healthLastPrice||entry),adverseStep=dir>0?exitPx<prev:exitPx>prev;
      let adverseTicks=Number(s.healthAdverseTicks||0);adverseTicks=adverseStep&&r<-.20?Math.min(30,adverseTicks+1):Math.max(0,adverseTicks-1);
      const bestR=Math.max(Number.isFinite(Number(s.healthBestR))?Number(s.healthBestR):r,r),worstR=Math.min(Number.isFinite(Number(s.healthWorstR))?Number(s.healthWorstR):r,r),style=String(s.style||'SCALP').toUpperCase(),rule=stableUniverseRule(style),tech=s.technicalAtIssue||{},spread=Number(q.spreadBps??tech.spreadBps??0),baseSpread=Math.max(.01,Number(tech.spreadBps??spread??.01)),turnover=Number(q.turnover24h||q.turnover24hQuote||tech.turnover24h||0),spreadStress=spread>Math.max(rule.maxSpread*1.40,baseSpread*MARKET_HEALTH_POLICY.spreadStressMultiplier),liquidityStress=turnover>0&&turnover<rule.minTurnover*MARKET_HEALTH_POLICY.liquidityStressRatio,giveback=bestR>=MARKET_HEALTH_POLICY.profitProtectStartR&&r<=bestR-MARKET_HEALTH_POLICY.profitGivebackR;
      let health='HEALTHY',reason='STRUCTURE_HOLDING';
      if(giveback){health='WARNING';reason='PROFIT_GIVEBACK';}
      else if(r<=MARKET_HEALTH_POLICY.warningR&&(adverseTicks>=3||spreadStress||liquidityStress)){health='WARNING';reason=spreadStress?'SPREAD_STRESS':liquidityStress?'LIQUIDITY_STRESS':'PERSISTENT_ADVERSE_MOVE';}
      else if(r<=MARKET_HEALTH_POLICY.watchR||spreadStress||liquidityStress){health='WATCH';reason=spreadStress?'SPREAD_WIDENING':liquidityStress?'LIQUIDITY_WEAKENING':'ADVERSE_EXCURSION';}
      let warningTicks=Number(s.healthWarningTicks||0);warningTicks=health==='WARNING'?Math.min(60,warningTicks+1):Math.max(0,warningTicks-1);
      const issued=Date.parse(s.issuedAt||s.triggeredAt||''),ageMs=Number.isFinite(issued)?Math.max(0,Date.now()-issued):0,minAge=style==='SWING'?MARKET_HEALTH_POLICY.minAgeBeforeCutMs.SWING:MARKET_HEALTH_POLICY.minAgeBeforeCutMs.SCALP;
      const emergency=ageMs>=10000&&r<=MARKET_HEALTH_POLICY.emergencyCutR,persistent=ageMs>=minAge&&r<=MARKET_HEALTH_POLICY.persistentCutR&&adverseTicks>=MARKET_HEALTH_POLICY.adverseTicksForCut&&warningTicks>=MARKET_HEALTH_POLICY.warningTicksForCut,stressed=ageMs>=minAge&&r<=MARKET_HEALTH_POLICY.stressedCutR&&warningTicks>=8&&adverseTicks>=4&&(spreadStress||liquidityStress),protect=ageMs>=minAge&&bestR>=MARKET_HEALTH_POLICY.profitProtectStartR&&r>0&&giveback&&adverseTicks>=4;
      if(emergency||persistent||stressed||protect){
        s.status='CLOSED';s.outcome='AUTO_CUT';s.lifecycle=protect?'AUTO_CUT_PROFIT_PROTECT':'AUTO_CUT_RISK_DETERIORATION';s.closedAt=at;s.exitPrice=exitPx;s.resultR=Number(r.toFixed(4));s.resolution='V3227_REALTIME_HEALTH_GUARD_SIGNAL_ONLY';s.healthState='CUT';s.healthReason=protect?'PROFIT_GIVEBACK':reason;s.manualAction='CLOSE_MANUALLY_AND_WAIT_REPLACEMENT';s.executionAction='SIGNAL_RETIRED_ONLY_NO_BROKER_EXECUTION';s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);const anyKey=`v31:active:any:${clean.market}:${clean.symbol}`,anyId=await this.env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===clean.id)await this.env.SIGNALS_KV.delete(anyKey);}
        delete reg[id];dirty=true;const evt={type:'AUTO_CUT',signal:clean,price:exitPx,at};changed.push(evt);this.broadcast({type:'signal_event',event:'AUTO_CUT',signal:clean,price:exitPx,receivedAt:at});continue;
      }
      const oldHealth=String(s.healthState||'HEALTHY');s.healthState=health;s.healthReason=reason;s.healthR=Number(r.toFixed(4));s.healthBestR=Number(bestR.toFixed(4));s.healthWorstR=Number(worstR.toFixed(4));s.healthAdverseTicks=adverseTicks;s.healthWarningTicks=warningTicks;s.healthLastPrice=exitPx;s.lastPrice=exitPx;s.lastCheckedAt=at;s.healthUpdatedAt=at;s.manualTradeMonitoring=true;s.executionAction='SIGNAL_ONLY_USER_MANUAL_EXECUTION';dirty=true;
      if(oldHealth!==health){const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;if(this.env?.SIGNALS_KV)await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});const event=health==='WARNING'?'HEALTH_WARNING':'HEALTH_WATCH';changed.push({type:event,signal:clean,price:exitPx,at});this.broadcast({type:'signal_event',event,signal:clean,price:exitPx,receivedAt:at});}
    }
    if(dirty)await this.persistRegistry();return changed;
  }
'''
w=block(w,'  async evaluate(market,rows,receivedAt){','  async fetch(req) {',evaluate,'evaluate')

monitor_cycle=r'''  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg),previous=(await this.state.storage.get('cryptoMonitorStatus'))||{},cycle=Number(previous.cycle||0)+1,at=nowIso();
    if(!active.length){const status={ok:true,running:false,cycle,activeCrypto:0,underfilledStyles:['SWING','SCALP'],receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);const pack={type:'crypto_quotes',ok:true,receivedAt:at,quotes:[],count:0};await this.state.storage.put('cryptoLiveQuotes',pack);this.broadcast(pack);return status;}
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[],liveQuotes=[];let quotes=0;
    for(const provider of providers){
      try{const snap=await cryptoSnapshotForProvider(this.env,provider);if(snap.live===false||!snap.rows?.length){errors.push(`${provider}:NO_LIVE_ROWS`);continue;}quotes+=snap.rows.length;const by=new Map((snap.rows||[]).map(q=>[canonical(q.symbol),q]));for(const s of active){const authority=String(s.executionPriceAuthority||s.provider||s.exchange||'BYBIT').toUpperCase();if(authority!==provider)continue;const q=by.get(canonical(s.symbol));if(!q)continue;liveQuotes.push({signalId:String(s.signalId||s.id||''),symbol:canonical(s.symbol),style:String(s.style||'').toUpperCase(),provider,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),healthState:s.healthState||'HEALTHY',receivedAt:snap.receivedAt||at});}events.push(...await this.evaluate('CRYPTO',snap.rows,snap.receivedAt||at));}catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}
    }
    const quotePack={type:'crypto_quotes',ok:liveQuotes.length>0,receivedAt:at,count:liveQuotes.length,quotes:liveQuotes,providers,errors};await this.state.storage.put('cryptoLiveQuotes',quotePack);this.broadcast(quotePack);
    const activeNow=this.activeRows(await this.registry()),underfilledStyles=['SWING','SCALP'].filter(st=>activeNow.filter(x=>String(x.style||'').toUpperCase()===st).length<styleTarget(st)),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,liveSignalQuotes:liveQuotes.length,events:events.length,healthEvents:events.filter(x=>String(x.type||'').startsWith('HEALTH_')).length,autoCuts:events.filter(x=>x.type==='AUTO_CUT').length,underfilledStyles,refillRequested:underfilledStyles.length>0,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});if(underfilledStyles.length)this.broadcast({type:'book_refill_needed',styles:underfilledStyles,receivedAt:at});return status;
  }
'''
w=block(w,'  async cryptoMonitorCycle(){','  async alarm(){',monitor_cycle,'crypto monitor cycle')

# Add active-signal fast read inside the DO before portfolio-snapshot route.
route_marker="    if(req.method==='GET'&&url.pathname==='/portfolio-snapshot'){return new Response(JSON.stringify(await this.portfolioSnapshot()),{headers:{'content-type':'application/json'}});}"
assert route_marker in w
w=w.replace(route_marker,"    if(req.method==='GET'&&url.pathname==='/active-signals'){const st=String(url.searchParams.get('style')||'').toUpperCase(),rows=this.activeRows(await this.registry()).filter(x=>!st||String(x.style||'').toUpperCase()===st);return new Response(JSON.stringify({ok:true,version:V3_VERSION,rows}),{headers:{'content-type':'application/json','cache-control':'no-store'}});}\n"+route_marker,1)

# ---------------------------------------------------------------------------
# Market-only candidate ranking and creation
# ---------------------------------------------------------------------------
insert_marker='function setupPriority(s){\n'
assert insert_marker in w
market_helpers=r'''function marketOnlySevenCandidate(raw){
  const s={...(raw||{})},style=String(s.style||'SCALP').toUpperCase(),dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,read=s.marketReadV322||{},tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{},cross=String(s.crossProviderConsensus?.state||'UNAVAILABLE').toUpperCase(),src=Number(s.sourcePrice||s.lastPrice||0),oldEntry=Number(s.entry),sl=Number(s.sl),t1=Number(s.tp1),t2=Number(s.tp2),t3=Number(s.tp3||s.tp);if(!(src>0&&oldEntry>0&&sl>0&&t1>0&&t2>0&&t3>0))return null;
  if(read.hardConflict||cross==='OPPOSED')return null;if(dir>0&&!(sl<src&&src<t1&&t1<t2&&t2<t3))return null;if(dir<0&&!(sl>src&&src>t1&&t1>t2&&t2>t3))return null;
  const oldRisk=Math.abs(oldEntry-sl),risk=Math.abs(src-sl);if(!(oldRisk>0&&risk>0))return null;const driftR=Math.abs(src-oldEntry)/oldRisk,rr=Math.abs(t3-src)/risk,spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),move=Math.abs(Number(tech.change24hPct||0)),ext=Math.abs(Number(tech.extensionAtr||read.extensionAtr||0)),rsi=Number(tech.rsi||50),rule=stableUniverseRule(style),contextAligned=read.contextAligned===true,contextStrong=read.contextStrong===true,execEvent=read.executionEvent===true||Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),momentum=read.executionMomentum===true,strict=read.marketEntryReady===true&&contextStrong&&execEvent&&momentum&&cross==='CONFIRMED';
  const safe=contextAligned&&momentum&&(execEvent||contextStrong)&&cross!=='OPPOSED'&&spread>=0&&spread<=rule.maxSpread&&turnover>=rule.minTurnover&&move<=rule.maxMove&&ext<=(style==='SWING'?.18:.23)&&driftR<=(style==='SWING'?.32:.36)&&(dir>0?rsi<=70:rsi>=30);if(!strict&&!safe)return null;
  const minRR=style==='SWING'?2.75:2.15;if(rr<minRR)return null;
  return {...s,orderType:'MARKET',entry:src,actualEntry:src,status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',targetRR:Number(rr.toFixed(3)),coverageFallback:false,marketOnly:true,marketOnlyQuality:strict?'STRICT_CONFIRMED':'TOP_CONTEXT_SAFE',marketOnlyFacts:{strict,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:momentum,crossProvider:cross,extensionAtr:Number(ext.toFixed(3)),driftR:Number(driftR.toFixed(3)),spreadBps:spread,turnover24h:turnover,targetRR:Number(rr.toFixed(3))},entryAssessment:{verdict:'PASS',method:'V3227_MARKET_ONLY_STRUCTURE_CONTEXT_LIQUIDITY_NO_WIN_PROBABILITY',failed:[]}};
}
function compareMarketOnlyQuality(a,b){
  const ax=a.marketOnlyQuality==='STRICT_CONFIRMED'?0:1,bx=b.marketOnlyQuality==='STRICT_CONFIRMED'?0:1;if(ax!==bx)return ax-bx;const af=a.marketOnlyFacts||{},bf=b.marketOnlyFacts||{};for(const k of ['contextStrong','executionEvent','executionMomentum']){const av=af[k]?0:1,bv=bf[k]?0:1;if(av!==bv)return av-bv;}if(String(af.crossProvider)!==String(bf.crossProvider)){if(af.crossProvider==='CONFIRMED')return-1;if(bf.crossProvider==='CONFIRMED')return 1;}if(Number(af.spreadBps)!==Number(bf.spreadBps))return Number(af.spreadBps)-Number(bf.spreadBps);if(Number(af.extensionAtr)!==Number(bf.extensionAtr))return Number(af.extensionAtr)-Number(bf.extensionAtr);if(Number(af.driftR)!==Number(bf.driftR))return Number(af.driftR)-Number(bf.driftR);if(Number(af.turnover24h)!==Number(bf.turnover24h))return Number(bf.turnover24h)-Number(af.turnover24h);return Number(bf.targetRR||0)-Number(af.targetRR||0);
}

'''
w=w.replace(insert_marker,market_helpers+insert_marker,1)

active_book=r'''async function getActiveBook(env){
  const p=await realtimeActiveSignals(env);return Array.isArray(p)?p.filter(s=>s&&s.status==='OPEN'&&String(s.engineVersion||'')===V3_VERSION&&String(s.orderType||'MARKET').toUpperCase()==='MARKET'):[];
}
'''
w=block(w,'async function getActiveBook(env){','async function retireLegacyActiveSignals',active_book,'getActiveBook')

# Fast active read helper next to realtime portfolio helper.
portfolio_helper='async function realtimePortfolioSnapshot(env)'
pos=w.find(portfolio_helper);assert pos>=0
# Insert helper after the function's one-line closing by locating next newline after its line.
line_end=w.find('\n',pos);assert line_end>=0
active_helper="\nasync function realtimeActiveSignals(env,style=''){const stub=mt5LiveStub(env);if(!stub)return[];try{const suffix=style?`?style=${encodeURIComponent(style)}`:'';const r=await stub.fetch('https://mt5-live/active-signals'+suffix);if(!r.ok)return[];const x=await r.json();return Array.isArray(x?.rows)?x.rows:[];}catch{return[];}}\n"
w=w[:line_end+1]+active_helper+w[line_end+1:]

maybe=r'''async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];
  const book=await getActiveBook(env),made=[],candidates=(setups||[]).map(marketOnlySevenCandidate).filter(Boolean).sort(compareMarketOnlyQuality);
  const activeTotal=()=>book.length,styleCount=()=>book.filter(x=>String(x.style||'').toUpperCase()===style).length;
  for(const rawSetup of candidates){
    if(made.length>=styleNewLimit(style)||activeTotal()>=PORTFOLIO_POLICY.maxActiveTotal||styleCount()>=styleTarget(style))break;
    const setup=stampMarketJudgment({...rawSetup},market,style);if(!validSignalStructure(setup))continue;if(book.some(x=>canonical(x.symbol)===canonical(setup.symbol)))continue;
    const issuedAt=nowIso(),id=`V3227M-CRYPTO-${style}-${canonical(setup.symbol)}-${Date.now().toString(36)}`,s=normalizeDisplaySignal({...setup,id,signalId:id,issuedAt,triggeredAt:issuedAt,actualEntry:Number(setup.entry),lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,portfolioPolicy:PORTFOLIO_POLICY,reservationMode:'DURABLE_OBJECT_ATOMIC_MARKET_ONLY',healthState:'HEALTHY',healthReason:'NEW_MARKET_SIGNAL',healthR:0,healthBestR:0,healthWorstR:0,healthAdverseTicks:0,healthWarningTicks:0,healthUpdatedAt:issuedAt,manualTradeMonitoring:true,executionAction:'SIGNAL_ONLY_USER_MANUAL_EXECUTION'},market,style),kvKey=v31Prefix(market,style)+id;
    const reservation=await reserveRealtimeSignal(env,s,kvKey);if(!reservation?.accepted)continue;s.portfolioReservation={accepted:true,mode:'DURABLE_OBJECT_ATOMIC_MARKET_ONLY',activeTotal:Number(reservation.activeTotal||0)};
    try{await writeV31Signal(env,s);}catch(e){await releaseRealtimeSignal(env,id);throw e;}made.push(s);book.push(s);
  }
  return made;
}

'''
w=block(w,'async function maybeCreateV31(env,market,style,setups){','async function analyzeCryptoBatch',maybe,'maybeCreateV31')

scan=r'''async function scanCrypto(env,style){
  style=String(style||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const trackerEvents=await retireAllLegacyActiveSignals(env),snap=await loadCryptoSnapshot(env);if(snap.live===false)return {ok:true,version:V3_VERSION,market:'CRYPTO',style,status:'NO_FRESH_CRYPTO_SNAPSHOT',created:0,provider:snap.provider,live:false,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY};
  const all=snap.rows,stable100=await persistStable100(env,snap,all),portfolio=await realtimePortfolioSnapshot(env),styleUnderfilled=Number(portfolio.styles?.[style]||0)<styleTarget(style),liquid=stable100.filter(x=>stableUniverseEligible(x,style));
  const rankedLimit=style==='SCALP'?(styleUnderfilled?Math.min(90,liquid.length):Math.min(48,liquid.length)):(styleUnderfilled?Math.min(80,liquid.length):Math.min(42,liquid.length)),ranked=rotatingStableCandidates(liquid,style,rankedLimit),rawAnalyses=await analyzeCryptoBatch(ranked,style,8),marketCandidates=rawAnalyses.map(marketOnlySevenCandidate).filter(Boolean).sort(compareMarketOnlyQuality),created=await maybeCreateV31(env,'CRYPTO',style,marketCandidates),after=await realtimePortfolioSnapshot(env);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_HEALTH',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:marketCandidates.length,strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='STRICT_CONFIRMED').length,safeFill:marketCandidates.filter(x=>x.marketOnlyQuality==='TOP_CONTEXT_SAFE').length,created:created.length,newSignals:created,activeAfter:after.styles?.[style]||0,targetActive:styleTarget(style),marketOnly:true,standby:{disabled:true,count:0},trackerEvents,portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.22.7 emits MARKET only. It fills 2 SWING first and 5 SCALP second from the strongest current structure/context candidates that pass live liquidity, anti-extension, target-path and cross-provider safety checks. No LIMIT/STOP fallback is permitted.'};
}

'''
w=block(w,'async function scanCrypto(env,style){','async function cryptoOnlyMaintenance(env){',scan,'scanCrypto')

maintenance=r'''async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SWING','SCALP']){const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'MARKET_REFILL':'FULL'}`);if(underfilled){await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);}}
  for(const style of ['SWING','SCALP'])if(Number(p.styles?.[style]||0)<styleTarget(style)){await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  await kickCryptoServerMonitor(env).catch(()=>{});return {mode:'EXACT_5_SCALP_2_SWING_MARKET_ONLY',attempted,portfolio:p,healthPolicy:MARKET_HEALTH_POLICY,standbys:{disabled:true}};
}

'''
w=block(w,'async function cryptoOnlyMaintenance(env){','async function exnessQuoteMap',maintenance,'maintenance')

# ---------------------------------------------------------------------------
# Active reads from DO; long-history statistics are paginated separately.
# ---------------------------------------------------------------------------
history_helper=r'''async function getV31HistorySignals(env,market,style,maxKeys=5000){
  if(!env?.SIGNALS_KV)return[];const prefix=v31Prefix(market,style),keys=[];let cursor=undefined,pages=0;
  do{const page=await env.SIGNALS_KV.list({prefix,limit:1000,...(cursor?{cursor}:{})});keys.push(...(page.keys||[]));pages++;if(page.list_complete||!page.cursor||keys.length>=maxKeys)break;cursor=page.cursor;}while(pages<5);
  const out=[];for(let i=0;i<Math.min(keys.length,maxKeys);i+=50){const raws=await Promise.all(keys.slice(i,i+50).map(k=>env.SIGNALS_KV.get(k.name)));for(const raw of raws){if(!raw)continue;try{out.push(JSON.parse(raw))}catch{}}}out.sort((a,b)=>Date.parse(b.issuedAt||0)-Date.parse(a.issuedAt||0));return out;
}

'''
marker='async function unifiedSignals(url,env,ctx){\n';assert marker in w;w=w.replace(marker,history_helper+marker,1)

signals=r'''async function unifiedSignals(url,env,ctx){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_HEALTH',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',status=String(url.searchParams.get('status')||'active').toLowerCase(),limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120))),targetActive=styleTarget(style);let rows=[];
  if(status==='active'){rows=(await realtimeActiveSignals(env,style)).map(x=>normalizeDisplaySignal(x,market,style)).filter(s=>s.status==='OPEN'&&String(s.engineVersion||'')===V3_VERSION&&String(s.orderType||'MARKET').toUpperCase()==='MARKET');const seen=new Set();rows=rows.filter(s=>{const sym=canonical(s.symbol);if(!sym||seen.has(sym))return false;seen.add(sym);return true;}).slice(0,Math.min(limit,targetActive));if(rows.length<targetActive&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));}
  else{rows=(await getV31Signals(env,market,style)).map(x=>normalizeDisplaySignal(x,market,style)).filter(s=>String(s.engineVersion||'')===V3_VERSION).filter(s=>status==='all'||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);}
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_HEALTH',market,style,status,targetActive,activeCount:status==='active'?rows.length:undefined,exactActive:status==='active'?rows.length===targetActive:undefined,marketOnly:true,signals:rows});
}

'''
w=block(w,'async function unifiedSignals(url,env,ctx){','async function unifiedPerformance',signals,'unifiedSignals')

perf=r'''async function unifiedPerformance(url,env){
  const requested=String(url.searchParams.get('market')||'CRYPTO').toUpperCase();if(requested!=='CRYPTO')return json({ok:false,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_HEALTH',error:'FOREX_DISABLED_CRYPTO_ONLY'},410);
  const market='CRYPTO',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=await getV31HistorySignals(env,market,style),active=rows.filter(s=>String(s.engineVersion||'')===V3_VERSION&&s.status==='OPEN'),tpSl=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),cuts=rows.filter(s=>s.status==='CLOSED'&&s.outcome==='AUTO_CUT'),allResolved=[...tpSl,...cuts],tp=tpSl.filter(s=>s.outcome==='TP').length,sl=tpSl.filter(s=>s.outcome==='SL').length,cutProfit=cuts.filter(s=>Number(s.resultR||0)>0).length,cutLoss=cuts.length-cutProfit,netR=allResolved.reduce((z,s)=>z+Number(s.resultR||0),0),wr=tpSl.length?tp/tpSl.length*100:null,allWins=allResolved.filter(s=>Number(s.resultR||0)>0).length,allWr=allResolved.length?allWins/allResolved.length*100:null;
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_HEALTH',market,style,performance:{retentionDays:365,total:rows.length,active:active.length,pending:0,open:active.length,resolved:tpSl.length,tp,sl,winRateResolved:wr,winRateLabel:tpSl.length?`${wr.toFixed(1)}% (${tp}/${tpSl.length})`:'CHƯA CÓ MẪU TP/SL',autoCut:cuts.length,autoCutProfit:cutProfit,autoCutLoss:cutLoss,allResolved:allResolved.length,allWins,winRateAllResolved:allWr,winRateAllLabel:allResolved.length?`${allWr.toFixed(1)}% (${allWins}/${allResolved.length})`:'CHƯA CÓ MẪU',netRResolved:Number(netR.toFixed(2)),sampleAdequate:allResolved.length>=50,policy:'TP_SL_WR_STRICT; AUTO_CUT_SEPARATE; ALL_EXIT_WR_INCLUDES_AUTO_CUT'}});
}

'''
w=block(w,'async function unifiedPerformance(url,env){','async function scanRoute',perf,'performance')

stability=r'''async function v315Stability(env){
  const portfolio=await realtimePortfolioSnapshot(env),monitor=await cryptoServerMonitorStatus(env),styles={};let totalResolved=0,totalTp=0,totalSl=0,totalCuts=0,totalAll=0,totalWins=0,totalNetR=0;
  for(const style of ['SCALP','SWING']){const rows=await getV31HistorySignals(env,'CRYPTO',style),tpSl=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),cuts=rows.filter(s=>s.status==='CLOSED'&&s.outcome==='AUTO_CUT'),tp=tpSl.filter(s=>s.outcome==='TP').length,sl=tpSl.filter(s=>s.outcome==='SL').length,all=[...tpSl,...cuts],wins=all.filter(s=>Number(s.resultR||0)>0).length,netR=all.reduce((z,s)=>z+Number(s.resultR||0),0),wr=tpSl.length?tp/tpSl.length*100:null,allWr=all.length?wins/all.length*100:null;styles[style]={resolved:tpSl.length,tp,sl,winRateResolved:wr,autoCut:cuts.length,allResolved:all.length,winRateAllResolved:allWr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:all.length>=50,evidenceState:all.length>=50?'MATURE_SAMPLE':all.length>=15?'BUILDING_SAMPLE':'INSUFFICIENT_SAMPLE'};totalResolved+=tpSl.length;totalTp+=tp;totalSl+=sl;totalCuts+=cuts.length;totalAll+=all.length;totalWins+=wins;totalNetR+=netR;}
  const monitorHealthy=monitor?.ok!==false&&monitor?.running!==false&&Array.isArray(monitor?.errors)&&monitor.errors.length===0,warnings=[];if(totalAll<50)warnings.push('PERFORMANCE_SAMPLE_SMALL');if(!monitorHealthy)warnings.push('CRYPTO_MONITOR_DEGRADED');if(!portfolio.exactTarget)warnings.push('ACTIVE_BOOK_NOT_EXACT_5_2');
  return json({ok:true,version:V3_VERSION,checkpoint:CHECKPOINT,mode:'CRYPTO_MARKET_ONLY_HEALTH',infrastructure:{state:monitorHealthy?'STABLE':'DEGRADED',monitor,portfolio},tradingEvidence:{state:totalAll>=100?'MATURE':'NOT_YET_PROVEN',retentionDays:365,resolvedTpSl:totalResolved,tp:totalTp,sl:totalSl,strictWinRateResolved:totalResolved?totalTp/totalResolved*100:null,autoCut:totalCuts,allResolved:totalAll,allExitWinRate:totalAll?totalWins/totalAll*100:null,netRResolved:Number(totalNetR.toFixed(2)),styles},warnings,note:'Win rates are descriptive historical outcomes, never predicted probabilities. Strict TP/SL WR is kept separate from AUTO_CUT outcomes.'});
}

'''
w=block(w,'async function v315Stability(env){','async function v3Status',stability,'stability')

status=r'''async function v3Status(env,ctx){
  const portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env),missing=['SCALP','SWING'].filter(st=>Number(portfolio.styles?.[st]||0)<styleTarget(st));if(missing.length&&ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_MARKET_ONLY_HEALTH',service:'SignalHub Crypto MARKET-only 5 SCALP + 2 SWING',checkpoint:CHECKPOINT,app:V31_RELEASE,crypto:{priceAuthority:'PROVIDER_PINNED_BYBIT_PREFERRED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'FIXED_5_MARKET_ONLY_5M_15M_1H',swing:'FIXED_2_MARKET_ONLY_1H_4H_1D',pendingLifecycle:'DISABLED',healthMonitor:'DURABLE_OBJECT_ALARM_1S',crossProviderContextCheck:true,marketReadVersion:'V3227_MARKET_ONLY_STRUCTURE_CONTEXT_LIQUIDITY',watchMode:'STABLE100_TAP_FOR_IDEAL_PLAN'},engines:{cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},forexDisabled:true,portfolio,missingStyles:missing,cryptoMonitor,healthPolicy:MARKET_HEALTH_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:'STRICT_TP_SL_HISTORY_PLUS_SEPARATE_AUTO_CUT_AND_ALL_EXIT_STATS_NOT_PREDICTED_PROBABILITY'});
}

'''
w=block(w,'async function v3Status(env,ctx){','async function handleV3',status,'status')

# Update Watchlist book metadata without changing read-only behavior.
w=w.replace('targetScalp:10,targetSwing:5','targetScalp:5,targetSwing:2')
w=w.replace('15 active slots','7 active slots').replace('the 15 active slots','the 7 active slots')

# ---------------------------------------------------------------------------
# Android: market-only UI, resilient live fallback, visible health warnings
# ---------------------------------------------------------------------------
a=a.replace('APP_VERSION="3.22.6"','APP_VERSION="3.22.7"')
a=a.replace('private static final long LIVE_REFRESH_MS=750L; // crypto WebSocket primary; REST watchdog fallback','private static final long LIVE_REFRESH_MS=1000L; // 1s WebSocket watchdog; REST only when stream is stale')
a=a.replace('CRYPTO • TOP 100 • 10 SCALP + 5 SWING','CRYPTO • MARKET ONLY • 5 SCALP + 2 SWING')
a=a.replace('10 SCALP + 5 SWING','5 SCALP + 2 SWING')
a=a.replace('style+" • CRYPTO REALTIME • "+(style.equals("SCALP")?"10 SLOT":"5 SLOT")','style+" • MARKET ONLY • "+(style.equals("SCALP")?"5 LỆNH":"2 LỆNH")')
a=a.replace('private volatile long fxStreamLastMs=0,cryptoStreamLastMs=0,lastCryptoStreamConnectAttemptMs=0,watchLastBulkMs=0,watchLastRenderMs=0;','private volatile long fxStreamLastMs=0,cryptoStreamLastMs=0,lastCryptoStreamConnectAttemptMs=0,cryptoUniverseLastMs=0,watchLastBulkMs=0,watchLastRenderMs=0;')

# Signal events that end a slot immediately request a background refill.
old='if("signal_event".equals(type)){JSONObject sig=p.optJSONObject("signal");if(sig!=null)applyRealtimeSignal(sig);return;}'
new='if("signal_event".equals(type)){JSONObject sig=p.optJSONObject("signal");String ev=p.optString("event","");if(sig!=null)applyRealtimeSignal(sig);if(ev.equals("AUTO_CUT")||ev.equals("TP")||ev.equals("SL")||ev.equals("CANCELLED"))io.execute(()->{try{ApiClient.get("/v3/status?appRefill="+System.currentTimeMillis());}catch(Throwable ignored){}});return;}'
assert old in a;a=a.replace(old,new,1)

# Primary fallback fetches only seven active quotes; Stable100 refresh is throttled.
refresh=r'''    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{boolean activeOk=false;try{
        JSONObject live=new JSONObject(ApiClient.getLive("/v3/crypto/live-active?mobile="+System.currentTimeMillis()));JSONArray q=live.optJSONArray("quotes");long received=parseMs(live.optString("receivedAt","")),now=System.currentTimeMillis();if(q!=null&&q.length()>0){for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:now);}}activeOk=true;cryptoLastOkMs=now;lastApiOkMs=now;cryptoState=(received>0&&now-received>3500)?"DELAYED":"LIVE";}
        if(screen.equals("WATCH")||cryptoPrices.isEmpty()||now-cryptoUniverseLastMs>5000){try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000"));JSONArray arr=p.optJSONArray("tickers");Map<String,JSONObject> next=new ConcurrentHashMap<>();if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject z=arr.optJSONObject(i);if(z!=null&&z.optDouble("lastPrice",0)>0)next.put(z.optString("symbol",""),z);}if(!next.isEmpty()){cryptoPrices.clear();cryptoPrices.putAll(next);cryptoUniverseLastMs=now;}cryptoProvider=p.optString("provider",cryptoProvider);cryptoCount=p.optInt("count",next.size());}catch(Throwable ignored){}}
    }catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;if(!activeOk)cryptoState=age<5000?"DELAYED":age<15000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("WATCH"))updateWatchUniversePrices();});}});}

'''
a=block(a,'    private void refreshCryptoLive(){','    private void updateConnectionViews(){',refresh,'android refreshCryptoLive')

# Market-only order label and health status helpers.
order_old='private String orderDisplay(JSONObject s,double px){if(isDisplayLive(s,px))return "LIVE";String o=s.optString("orderType","MARKET").toUpperCase(Locale.US);return o.equals("LIMIT")?"LIMIT":o.equals("STOP")?"STOP":"MARKET";}\n    private int orderColor(JSONObject s,double px){String o=orderDisplay(s,px);return o.equals("LIVE")?GREEN:o.equals("LIMIT")?YELLOW:o.equals("STOP")?BLUE:CYAN;}'
order_new='private String orderDisplay(JSONObject s,double px){return isDisplayLive(s,px)?"MARKET LIVE":"MARKET";}\n    private int orderColor(JSONObject s,double px){return isDisplayLive(s,px)?GREEN:CYAN;}'
assert order_old in a;a=a.replace(order_old,order_new,1)

health_helpers=r'''    private String healthLabel(JSONObject s){String h=s.optString("healthState","HEALTHY").toUpperCase(Locale.US);if(h.equals("WARNING"))return "⚠ CẢNH BÁO";if(h.equals("WATCH"))return "THEO DÕI";if(h.equals("CUT"))return "CẮT TÍN HIỆU";return "ỔN ĐỊNH";}
    private int healthColor(JSONObject s){String h=s.optString("healthState","HEALTHY").toUpperCase(Locale.US);return h.equals("WARNING")||h.equals("WATCH")?YELLOW:h.equals("CUT")?RED:GREEN;}
'''
marker='    private String historicalWr(String market,String st){';assert marker in a;a=a.replace(marker,health_helpers+marker,1)
a=a.replace('return "WR lịch sử "+p.optString("winRateLabel","—");','return "WR TP/SL "+p.optString("winRateLabel","—");')

old='private String tradeStatusText(JSONObject s,double px){if(!isDisplayLive(s,px))return pendingDistanceText(s,px);double r=currentR(s,px),rr=targetR(s);if(r<0){int pct=(int)Math.round(Math.min(100,Math.max(0,-r*100)));return String.format(Locale.US,"ÂM  %+.2fR  •  %d%% TỚI SL",r,pct);}int pct=(int)Math.round(Math.min(100,Math.max(0,r/Math.max(.1,rr)*100)));return String.format(Locale.US,"DƯƠNG  %+.2fR  •  %d%% TỚI TP3",r,pct);}\n    private int tradeStatusColor(JSONObject s,double px){if(!isDisplayLive(s,px))return orderColor(s,px);return currentR(s,px)>=0?GREEN:RED;}'
new='private String tradeStatusText(JSONObject s,double px){double r=currentR(s,px),rr=targetR(s);String h=healthLabel(s);if(r<0){int pct=(int)Math.round(Math.min(100,Math.max(0,-r*100)));return String.format(Locale.US,"%s • %+.2fR • %d%% TỚI SL",h,r,pct);}int pct=(int)Math.round(Math.min(100,Math.max(0,r/Math.max(.1,rr)*100)));return String.format(Locale.US,"%s • %+.2fR • %d%% TỚI TP3",h,r,pct);}\n    private int tradeStatusColor(JSONObject s,double px){String h=s.optString("healthState","HEALTHY").toUpperCase(Locale.US);if(h.equals("WARNING")||h.equals("WATCH"))return YELLOW;if(h.equals("CUT"))return RED;return currentR(s,px)>=0?GREEN:RED;}'
assert old in a;a=a.replace(old,new,1)

# Replace signal list screen: no LIMIT/STOP sections.
render=r'''    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();int target=style.equals("SCALP")?5:2;subtitle.setText(style+" • MARKET ONLY • "+target+" LỆNH");
            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>();int warning=0;for(JSONObject x:rows){if("OPEN".equalsIgnoreCase(x.optString("status",""))&&"MARKET".equalsIgnoreCase(x.optString("orderType","MARKET"))){liveRows.add(x);String h=x.optString("healthState","HEALTHY");if(h.equalsIgnoreCase("WATCH")||h.equalsIgnoreCase("WARNING"))warning++;}}
            LinearLayout top=row();LinearLayout title=column();title.addView(tv(style,20,TEXT,true));title.addView(tv(style.equals("SCALP")?"5 MARKET • 5m / 15m / 1h":"2 MARKET • 1h / 4h / 1D",9,MUTED,false));top.addView(title,new LinearLayout.LayoutParams(0,-2,1f));top.addView(chip(cryptoState,stateColor(cryptoState)));content.addView(top);
            LinearLayout stats=row();View live=miniStat("MARKET LIVE",liveRows.size()+" / "+target,"duy nhất MARKET",liveRows.size()==target?GREEN:YELLOW),health=miniStat("BOT GIÁM SÁT",String.valueOf(warning),warning==0?"không cảnh báo":"cần theo dõi",warning==0?GREEN:YELLOW);LinearLayout.LayoutParams p1=new LinearLayout.LayoutParams(0,-2,1f);p1.setMargins(0,dp(8),dp(4),dp(7));LinearLayout.LayoutParams p2=new LinearLayout.LayoutParams(0,-2,1f);p2.setMargins(dp(4),dp(8),0,dp(7));stats.addView(live,p1);stats.addView(health,p2);content.addView(stats);content.addView(tv(performanceSummary(),9,MUTED,false));
            addCryptoSignalGroup("MARKET ĐANG CHẠY",liveRows,warning>0?YELLOW:GREEN);
        };if(animate)swap(body);else body.run();
    }

'''
a=block(a,'    private void renderSignals(boolean animate){','    private String performanceSummary(){',render,'renderSignals')

perf_ui='    private String performanceSummary(){JSONObject p=perfCache.get("CRYPTO:"+style);if(p==null)return "Chưa đủ dữ liệu đóng lệnh";int strict=p.optInt("resolved",0),cuts=p.optInt("autoCut",0),all=p.optInt("allResolved",0);String wr=p.optString("winRateLabel","—"),allWr=p.optString("winRateAllLabel","—");return "WR TP/SL "+wr+" • EXIT WR "+allWr+" • CUT "+cuts+" • "+all+" mẫu • Net "+String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0));}\n'
a=block(a,'    private String performanceSummary(){','    private View signalCard(JSONObject s){',perf_ui,'performanceSummary UI')

# Visible health line in detail panel.
old='trade.addView(pnl);pnlViews.put(id,pnl);'
new='trade.addView(pnl);pnlViews.put(id,pnl);TextView hv=tv("BOT GIÁM SÁT: "+healthLabel(s)+" • "+s.optString("healthReason","STRUCTURE_HOLDING").replace(\'_\',\' \'),10,healthColor(s),true);hv.setPadding(0,dp(5),0,0);trade.addView(hv);TextView manual=tv("AUTO-CUT chỉ đóng tín hiệu trên app; nếu bạn đã vào lệnh thủ công thì hãy đóng vị thế theo cảnh báo.",9,MUTED,false);manual.setPadding(0,dp(4),0,0);trade.addView(manual);'
assert old in a;a=a.replace(old,new,1)

# Android network/build identity.
c=c.replace('SignalHub-Android/3.22.6','SignalHub-Android/3.22.7')
m=m.replace('SignalHub V3.22.6','SignalHub V3.22.7').replace('10 SCALP + 5 SWING','5 SCALP + 2 SWING').replace(' / 15 active',' / 7 active')
g=g.replace('versionCode 35','versionCode 36').replace("versionName '3.22.6'","versionName '3.22.7'")

# Background monitor: exact 5/2, 2-second refill request, health-state notifications.
m=m.replace('private static final long REFILL_CHECK_MS=30000L;','private static final long REFILL_CHECK_MS=2000L;')
sync=r'''    private void syncAll(){
        int active=0,failed=0,missing=0;
        for(String style:new String[]{"SCALP","SWING"}){int styleActive=0,target="SCALP".equals(style)?5:2;try{JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market=CRYPTO&style="+style+"&status=all&limit=120"));JSONArray arr=root.optJSONArray("signals");if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject s=arr.optJSONObject(i);if(s==null)continue;String st=s.optString("status","");if("OPEN".equals(st)&&"MARKET".equalsIgnoreCase(s.optString("orderType","MARKET"))){active++;styleActive++;}process("CRYPTO",style,s,"SERVER_HEALTH_MONITORED");}}catch(Throwable e){failed++;}if(styleActive<target)missing++;}
        long now=System.currentTimeMillis();if(missing>0&&now-lastRefillCheck>=REFILL_CHECK_MS){try{ApiClient.get("/v3/status?mobileRefill="+now);}catch(Throwable ignored){}lastRefillCheck=now;}
        NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(n!=null){String text=failed==0?"CRYPTO LIVE • "+active+" / 7 • 5 SCALP + 2 SWING MARKET":"DEGRADED • "+failed+"/2 luồng • "+active+" / 7 MARKET";n.notify(FOREGROUND_ID,monitor(text));}
    }

'''
m=block(m,'    private void syncAll(){','    private void process(',sync,'monitor syncAll')

process=r'''    private void process(String market,String style,JSONObject s,String dataState){
        String id=s.optString("signalId",s.optString("id",""));if(id.isEmpty())return;String status=s.optString("status",""),outcome=s.optString("outcome",""),health=s.optString("healthState","HEALTHY").toUpperCase(Locale.US),state=status+":"+outcome+":"+health;SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);String key="state_"+id,old=p.getString(key,null);if(old==null){p.edit().putString(key,state).apply();if(isRecent(s.optString("issuedAt","")))notifySignal("MỚI • MARKET",market,style,s,dataState,id+":new");return;}if(old.equals(state))return;p.edit().putString(key,state).apply();
        if("CLOSED".equals(status)&&"AUTO_CUT".equals(outcome))notifySignal("CẮT TÍN HIỆU • ĐÓNG THỦ CÔNG",market,style,s,dataState,id+":autocut");
        else if("CLOSED".equals(status)&&"TP".equals(outcome))notifySignal("TP ĐẠT",market,style,s,dataState,id+":tp");
        else if("CLOSED".equals(status)&&"SL".equals(outcome))notifySignal("SL CHẠM",market,style,s,dataState,id+":sl");
        else if("OPEN".equals(status)&&"WARNING".equals(health))notifySignal("⚠ CẢNH BÁO LỆNH",market,style,s,dataState,id+":warning:"+s.optString("healthReason",""));
    }

'''
m=block(m,'    private void process(','    private void notifySignal(',process,'monitor process')

old='        b.append("\\n").append(market).append(" • ").append(s.optString("orderType","MARKET"));'
new='        b.append("\\n").append(market).append(" • MARKET");String health=s.optString("healthState","");if(!health.isEmpty())b.append(" • BOT ").append(health);String hr=s.optString("healthReason","");if(!hr.isEmpty())b.append(" • ").append(hr.replace(\'_\',\' \'));if("AUTO_CUT".equals(s.optString("outcome","")))b.append("\\nAUTO-CUT chỉ retire tín hiệu; hãy đóng vị thế thủ công nếu bạn đã vào lệnh.");'
assert old in m;m=m.replace(old,new,1)

worker.write_text(w);activity.write_text(a);api.write_text(c);monitor.write_text(m);gradle.write_text(g)

# Source invariants for CI and future checkpoints.
assert 'SIGNALHUB-V3-GATEWAY-3.22.7' in w
assert "const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_20';" in w
assert 'MARKET_ONLY_TOP_5_SCALP_2_SWING' in w and 'maxActiveTotal:7' in w
assert "function styleTarget(style){return String(style||'').toUpperCase()==='SWING'?2:5;}" in w
assert 'MARKET_HEALTH_POLICY' in w and "outcome='AUTO_CUT'" in w
assert 'marketOnlySevenCandidate' in w and 'compareMarketOnlyQuality' in w
assert "String(signal.orderType||'MARKET').toUpperCase()==='MARKET'" in w
assert 'APP_VERSION="3.22.7"' in a and 'MARKET ONLY' in a and 'healthLabel' in a
assert 'SignalHub-Android/3.22.7' in c
assert 'REFILL_CHECK_MS=2000L' in m and 'ĐÓNG THỦ CÔNG' in m
assert 'versionCode 36' in g and "versionName '3.22.7'" in g
print('patched SignalHub V3.22.7 market-only health seven')
