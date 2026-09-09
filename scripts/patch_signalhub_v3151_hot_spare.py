from pathlib import Path

P=Path('signalhub-worker/gateway-v3.js')
s=P.read_text()

def rep(old,new,label):
    global s
    if old not in s:
        raise SystemExit(f'{label}: marker missing')
    s=s.replace(old,new,1)

def insert_before(anchor,text,label):
    global s
    if anchor not in s:
        raise SystemExit(f'{label}: anchor missing')
    s=s.replace(anchor,text+anchor,1)

rep("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.15.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.15.1';",'version')
rep("cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true}","cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:3,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC',forexDisabled:true}",'top policy hot spare')
rep("cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',forexDisabled:true});","cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S',standbyPerStyle:3,replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC',forexDisabled:true});",'runtime policy hot spare')

methods=r'''  async setStandbys(payload){
    const style=String(payload?.style||'').toUpperCase();if(!['SCALP','SWING'].includes(style))return {ok:false,error:'BAD_STYLE'};
    const reg=await this.registry(),active=this.activeRows(reg),activeSymbols=new Set(active.map(x=>canonical(x.symbol))),rows=[],seen=new Set();
    for(const raw of (Array.isArray(payload?.signals)?payload.signals:[])){
      if(rows.length>=Number(PORTFOLIO_POLICY.standbyPerStyle||3))break;
      const s={...(raw||{})},symbol=canonical(s.symbol),order=String(s.orderType||'').toUpperCase();
      if(!symbol||seen.has(symbol)||activeSymbols.has(symbol))continue;
      if(String(s.market||'CRYPTO').toUpperCase()!=='CRYPTO'||String(s.style||style).toUpperCase()!==style)continue;
      if(!['LIMIT','STOP'].includes(order)||!validSignalStructure(s))continue;
      const assessment=s.entryAssessment?.verdict==='PASS'?s.entryAssessment:(s.coverageFallback?assessCoverageSetup(s):assessEntrySetup(s));if(assessment?.verdict!=='PASS')continue;
      rows.push({...s,market:'CRYPTO',style,status:'PENDING',entryState:'PENDING_ENTRY',entryAssessment:assessment,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,standbyPreparedAt:nowIso()});seen.add(symbol);
    }
    const pack={style,preparedAt:Date.now(),receivedAt:nowIso(),rows};await this.state.storage.put(`standby:${style}`,pack);return {ok:true,style,count:rows.length,symbols:rows.map(x=>x.symbol)};
  }
  async standbySnapshot(){
    const out={};for(const style of ['SCALP','SWING']){const p=(await this.state.storage.get(`standby:${style}`))||{style,preparedAt:null,rows:[]};out[style]={preparedAt:p.preparedAt||null,ageMs:p.preparedAt?Math.max(0,Date.now()-Number(p.preparedAt)):null,count:Array.isArray(p.rows)?p.rows.length:0,symbols:Array.isArray(p.rows)?p.rows.map(x=>x.symbol):[]};}return out;
  }
  async promoteStandby(style,reason='AUTO_REPLACE'){
    style=String(style||'').toUpperCase();if(!['SCALP','SWING'].includes(style))return {ok:false,promoted:[],error:'BAD_STYLE'};
    const key=`standby:${style}`,pack=(await this.state.storage.get(key))||{style,preparedAt:0,rows:[]},pool=Array.isArray(pack.rows)?[...pack.rows]:[],promoted=[];
    let reg=await this.registry(),active=this.activeRows(reg),styleCount=active.filter(x=>String(x.style||'').toUpperCase()===style).length;
    const maxAge=style==='SCALP'?10*60*1000:60*60*1000;if(pack.preparedAt&&Date.now()-Number(pack.preparedAt)>maxAge)pool.splice(0,pool.length);
    while(styleCount<Number(PORTFOLIO_POLICY.targetActivePerStyle||2)&&pool.length){
      const raw=pool.shift(),symbol=canonical(raw?.symbol),order=String(raw?.orderType||'').toUpperCase();if(!symbol||!['LIMIT','STOP'].includes(order)||!validSignalStructure(raw))continue;
      active=this.activeRows(reg);if(active.some(x=>canonical(x.symbol)===symbol))continue;
      const cluster=cryptoRiskCluster(symbol),clusterCount=active.filter(x=>cryptoRiskCluster(x.symbol)===cluster).length;if(cluster==='MEME'&&clusterCount>=PORTFOLIO_POLICY.maxMemeActiveTotal)continue;if(clusterCount>=PORTFOLIO_POLICY.maxActivePerRiskCluster)continue;
      if(active.length>=PORTFOLIO_POLICY.maxActiveTotal||active.filter(x=>String(x.style||'').toUpperCase()===style).length>=PORTFOLIO_POLICY.maxActivePerStyle)break;
      const issuedAt=nowIso(),id=`V315R-CRYPTO-${style}-${symbol}-${Date.now().toString(36)}`,s={...raw,id,signalId:id,market:'CRYPTO',style,symbol,status:'PENDING',entryState:'PENDING_ENTRY',lifecycle:'PENDING_ENTRY',issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,riskCluster:cluster,coverageReplacement:true,replacementReason:reason,reservationMode:'DURABLE_OBJECT_HOT_SPARE_PROMOTION',portfolioPolicy:PORTFOLIO_POLICY};
      const kvKey=`v31:signal:CRYPTO:${style}:${id}`;reg[id]={...s,kvKey};styleCount++;promoted.push(s);
      if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.put(`v31:active:CRYPTO:${style}:${symbol}`,id,{expirationTtl:SIGNAL_TTL});await this.env.SIGNALS_KV.put(`v31:active:any:CRYPTO:${symbol}`,id,{expirationTtl:SIGNAL_TTL});}
      this.broadcast({type:'signal_event',event:'HOT_SPARE_PROMOTED',signal:s,receivedAt:issuedAt});
    }
    this.signalRegistry=reg;await this.state.storage.put('signalRegistry',reg);await this.state.storage.put(key,{...pack,rows:pool,updatedAt:Date.now()});return {ok:true,style,promoted:promoted.map(x=>({id:x.id,symbol:x.symbol,orderType:x.orderType})),remaining:pool.length};
  }
'''
insert_before("  async evaluate(market,rows,receivedAt){\n",methods,'DO hot spare methods')

rep("    const status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:active.length,providers,quotes,events:events.length,errors,receivedAt:at};\n    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;","    const depleted=[...new Set(events.filter(e=>['CANCELLED','TP','SL'].includes(String(e?.type||''))).map(e=>String(e?.signal?.style||'').toUpperCase()).filter(x=>['SCALP','SWING'].includes(x)))],replacements=[];\n    for(const style of depleted){const r=await this.promoteStandby(style,'LIFECYCLE_EVENT');if(r?.promoted?.length)replacements.push({style,...r});}\n    const activeNow=this.activeRows(await this.registry()),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,events:events.length,replacements,errors,receivedAt:at};\n    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;",'monitor auto promote')

rep("    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/kick-crypto-monitor'){return new Response(JSON.stringify(await this.ensureCryptoMonitor(25)),{headers:{'content-type':'application/json'}});}","    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/set-standbys'){const p=await req.json();return new Response(JSON.stringify(await this.setStandbys(p)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/promote-standby'){const p=await req.json();return new Response(JSON.stringify(await this.promoteStandby(p?.style,p?.reason||'EXTERNAL_REFILL')),{headers:{'content-type':'application/json'}});}\n    if(req.method==='GET'&&url.pathname==='/standbys'){return new Response(JSON.stringify(await this.standbySnapshot()),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/kick-crypto-monitor'){return new Response(JSON.stringify(await this.ensureCryptoMonitor(25)),{headers:{'content-type':'application/json'}});}",'DO standby routes')

helpers=r'''async function setCryptoStandbys(env,style,signals){const stub=mt5LiveStub(env);if(!stub)return {ok:false,count:0};try{const r=await stub.fetch('https://mt5-live/set-standbys',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({style,signals})});return r.ok?await r.json():{ok:false,count:0};}catch(e){return {ok:false,count:0,error:String(e?.message||e)};}}
async function promoteCryptoStandby(env,style,reason='EXTERNAL_REFILL'){const stub=mt5LiveStub(env);if(!stub)return {ok:false,promoted:[]};try{const r=await stub.fetch('https://mt5-live/promote-standby',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({style,reason})});return r.ok?await r.json():{ok:false,promoted:[]};}catch(e){return {ok:false,promoted:[],error:String(e?.message||e)};}}
async function cryptoStandbyStatus(env){const stub=mt5LiveStub(env);if(!stub)return {};try{const r=await stub.fetch('https://mt5-live/standbys');return r.ok?await r.json():{};}catch{return {};}}
'''
insert_before("async function kickCryptoServerMonitor(env){",helpers,'standby helper functions')

old="""  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.15 fixed 2x2 book: strict setups are preferred; if a style would fall below two active ideas, best-available conditional LIMIT/STOP setups may fill coverage slots while hard structure, liquidity, spread, invalidation and target-path checks remain mandatory.'};
"""
new="""  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=analyses.filter(x=>!activeSymbols.has(canonical(x.symbol))&&['LIMIT','STOP'].includes(String(x.orderType||'').toUpperCase())).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),standby,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.15.1 fixed 2x2 book with hot spares: strict setups are preferred; conditional LIMIT/STOP coverage remains hard-safety checked, and the Durable Object promotes a prepared spare immediately after TP/SL/cancellation when possible.'};
"""
rep(old,new,'scan standby preparation')

old_maint="""async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    if(Number(p.styles?.[style]||0)>=PORTFOLIO_POLICY.minActivePerStyle)continue;
    attempted.push(style);await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {attempted,portfolio:p};
}
"""
new_maint="""async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    const underfilled=Number(p.styles?.[style]||0)<PORTFOLIO_POLICY.minActivePerStyle;attempted.push(`${style}:${underfilled?'REFILL':'STANDBY_REFRESH'}`);await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
    if(Number(p.styles?.[style]||0)<PORTFOLIO_POLICY.targetActivePerStyle){await promoteCryptoStandby(env,style,'MAINTENANCE_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {attempted,portfolio:p,standbys:await cryptoStandbyStatus(env)};
}
"""
rep(old_maint,new_maint,'maintenance hot spare refresh')

old_read="""  if(status==='active'&&rows.length<PORTFOLIO_POLICY.targetActivePerStyle){
    await scanCrypto(env,style).catch(()=>{});
    let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));
    rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);
  }
"""
new_read="""  if(status==='active'&&rows.length<PORTFOLIO_POLICY.targetActivePerStyle){
    for(let attempt=0;attempt<3&&rows.length<PORTFOLIO_POLICY.targetActivePerStyle;attempt++){
      await promoteCryptoStandby(env,style,'ACTIVE_READ_REFILL').catch(()=>{});await scanCrypto(env,style).catch(()=>{});await promoteCryptoStandby(env,style,'ACTIVE_READ_REFILL_AFTER_SCAN').catch(()=>{});
      let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);
    }
  }
"""
rep(old_read,new_read,'active read refill loop')

rep("if(url.pathname==='/v3/portfolio'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',portfolio:await realtimePortfolioSnapshot(env),policy:PORTFOLIO_POLICY});","if(url.pathname==='/v3/portfolio'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',portfolio:await realtimePortfolioSnapshot(env),policy:PORTFOLIO_POLICY});\n    if(url.pathname==='/v3/standbys'&&req.method==='GET')return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',standbys:await cryptoStandbyStatus(env)});",'public standby diagnostics')

cp=Path('SIGNALHUB_V3_CHECKPOINT_07_FIXED_2X2.md')
if cp.exists():
    cp.write_text(cp.read_text()+"""\n## V3.15.1 hot-spare refinement\n- Durable Object keeps up to 3 prepared pending candidates per style.\n- A TP, SL or pending cancellation triggers atomic hot-spare promotion for the depleted style.\n- Standbys are not shown as active orders until promoted.\n- Cron maintenance refreshes standby pools even while the 2x2 book is full.\n- Active reads also perform bounded refill attempts if a race leaves a style temporarily underfilled.\n""")
P.write_text(s)
print('patched SignalHub V3.15.1 hot-spare replacement')
