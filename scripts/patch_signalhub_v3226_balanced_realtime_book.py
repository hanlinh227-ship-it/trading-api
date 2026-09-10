from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
api=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
monitor=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
gradle=Path('signalhub-android/app/build.gradle')

w=worker.read_text(); a=activity.read_text(); c=api.read_text(); m=monitor.read_text(); g=gradle.read_text()

# Identity: distinguish this balanced allocator from the deployed-but-underfilled V3.22.5 runtime.
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.5','SIGNALHUB-V3-GATEWAY-3.22.6')
w=w.replace("versionName: '3.22.5'","versionName: '3.22.6'")
w=w.replace("title: 'SignalHub 3.22.5 Realtime Unique Book'","title: 'SignalHub 3.22.6 Balanced Realtime Book'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.5-Realtime-Unique-Book'","artifactName: 'SignalHub-Android-v3.22.6-Balanced-Realtime-Book'")

# Keep a deeper reserve so the 1-second lifecycle monitor can refill without waiting for a new deep scan.
w=w.replace('standbyPerStyle:20','standbyPerStyle:40')

# Add a safe style rebalance primitive inside the Durable Object.
# SWING may reclaim only a SCALP PENDING symbol when SWING is below 5.
# OPEN trades are never migrated/cancelled by this balancing path.
marker='''  async promoteStandby(style,reason='AUTO_REPLACE'){\n'''
assert marker in w, 'promoteStandby marker missing'
rebalance=r'''  async rebalanceForStyle(payload){
    const style=String(payload?.style||'').toUpperCase();
    if(style!=='SWING')return {ok:true,style,released:[],reason:'SWING_PRIORITY_ONLY'};
    const requested=[...new Set((Array.isArray(payload?.symbols)?payload.symbols:[]).map(canonical).filter(Boolean))];
    if(!requested.length)return {ok:true,style,released:[],reason:'NO_CANDIDATES'};
    let released=[],nextReg={};
    await this.state.storage.transaction(async txn=>{
      const reg=(await txn.get('signalRegistry'))||{},active=this.activeRows(reg),swingCount=active.filter(x=>String(x.style||'').toUpperCase()==='SWING').length,deficit=Math.max(0,styleTarget('SWING')-swingCount);
      if(deficit<=0){nextReg=reg;return;}
      const bySymbol=new Map(active.map(x=>[canonical(x.symbol),x]));
      for(const symbol of requested){
        if(released.length>=deficit)break;
        const old=bySymbol.get(symbol);if(!old)continue;
        if(String(old.style||'').toUpperCase()!=='SCALP'||String(old.status||'').toUpperCase()!=='PENDING')continue;
        const id=String(old.id||old.signalId||'');if(!id||!reg[id])continue;
        delete reg[id];released.push({...old});bySymbol.delete(symbol);
      }
      await txn.put('signalRegistry',reg);nextReg=reg;
    });
    this.signalRegistry=nextReg;
    const at=nowIso(),events=[];
    for(const old of released){
      const id=String(old.id||old.signalId||''),symbol=canonical(old.symbol),kvKey=String(old.kvKey||`v31:signal:CRYPTO:SCALP:${id}`),clean={...old,status:'CANCELLED',entryState:'CANCELLED',lifecycle:'STYLE_REBALANCED_BEFORE_ENTRY',outcome:'STYLE_REBALANCE',cancelledAt:at,lastCheckedAt:at,resolution:'V3226_SWING_PRIORITY_PENDING_REBALANCE',performanceEligible:false};delete clean.kvKey;
      if(this.env?.SIGNALS_KV){
        await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});
        await this.env.SIGNALS_KV.delete(`v31:active:CRYPTO:SCALP:${symbol}`);
        const anyKey=`v31:active:any:CRYPTO:${symbol}`,anyId=await this.env.SIGNALS_KV.get(anyKey);if(!anyId||anyId===id)await this.env.SIGNALS_KV.delete(anyKey);
      }
      const evt={type:'CANCELLED',event:'STYLE_REBALANCE',signal:clean,receivedAt:at};events.push(evt);this.broadcast({type:'signal_event',event:'CANCELLED',signal:clean,receivedAt:at});
    }
    return {ok:true,style,released:released.map(x=>({id:x.id||x.signalId,symbol:canonical(x.symbol),fromStyle:'SCALP',status:x.status})),events};
  }
'''
w=w.replace(marker,rebalance+marker,1)

# Expose the rebalance method only internally through the existing Durable Object stub.
old="if(req.method==='POST'&&url.pathname==='/promote-standby'){const p=await req.json();return new Response(JSON.stringify(await this.promoteStandby(p?.style,p?.reason||'EXTERNAL_REFILL')),{headers:{'content-type':'application/json'}});}"
new="if(req.method==='POST'&&url.pathname==='/rebalance-for-style'){const p=await req.json();return new Response(JSON.stringify(await this.rebalanceForStyle(p)),{headers:{'content-type':'application/json'}});}\n    "+old
assert old in w, 'promote standby DO route missing'
w=w.replace(old,new,1)

# Worker-side helper for the internal rebalance call.
marker="async function promoteCryptoStandby(env,style,reason='EXTERNAL_REFILL'){const stub=mt5LiveStub(env);if(!stub)return {ok:false,promoted:[]};try{const r=await stub.fetch('https://mt5-live/promote-standby',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({style,reason})});return r.ok?await r.json():{ok:false,promoted:[]};}catch(e){return {ok:false,promoted:[],error:String(e?.message||e)};}}"
assert marker in w, 'promoteCryptoStandby helper missing'
helper=marker+"\nasync function rebalanceCryptoStyle(env,style,signals){const stub=mt5LiveStub(env);if(!stub)return {ok:false,released:[]};const symbols=(signals||[]).map(x=>canonical(x?.symbol)).filter(Boolean);if(!symbols.length)return {ok:true,released:[]};try{const r=await stub.fetch('https://mt5-live/rebalance-for-style',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({style,symbols})});return r.ok?await r.json():{ok:false,released:[]};}catch(e){return {ok:false,released:[],error:String(e?.message||e)};}}"
w=w.replace(marker,helper,1)

# Every monitor tick tries to refill any underfilled style from already-prepared hot spares.
# This costs no deep candle scan and closes the gap immediately after a TP/SL/cancel when possible.
old="""    const depleted=[...new Set(events.filter(e=>['CANCELLED','TP','SL'].includes(String(e?.type||''))).map(e=>String(e?.signal?.style||'').toUpperCase()).filter(x=>['SCALP','SWING'].includes(x)))],replacements=[];
    for(const style of depleted){const r=await this.promoteStandby(style,'LIFECYCLE_EVENT');if(r?.promoted?.length)replacements.push({style,...r});}
    const activeNow=this.activeRows(await this.registry()),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,liveSignalQuotes:liveQuotes.length,events:events.length,replacements,errors,receivedAt:at};"""
new="""    const depleted=[...new Set(events.filter(e=>['CANCELLED','TP','SL'].includes(String(e?.type||''))).map(e=>String(e?.signal?.style||'').toUpperCase()).filter(x=>['SCALP','SWING'].includes(x)))],replacements=[];
    let beforeRefill=this.activeRows(await this.registry());const underfilled=['SWING','SCALP'].filter(st=>beforeRefill.filter(x=>String(x.style||'').toUpperCase()===st).length<styleTarget(st)),refillStyles=[...new Set([...depleted,...underfilled])];
    for(const style of refillStyles){const r=await this.promoteStandby(style,depleted.includes(style)?'LIFECYCLE_EVENT':'ONE_SECOND_TARGET_REFILL');if(r?.promoted?.length)replacements.push({style,...r});}
    const activeNow=this.activeRows(await this.registry()),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,liveSignalQuotes:liveQuotes.length,events:events.length,replacements,underfilledStyles:['SWING','SCALP'].filter(st=>activeNow.filter(x=>String(x.style||'').toUpperCase()===st).length<styleTarget(st)),errors,receivedAt:at};"""
assert old in w, 'V3.22.5 monitor refill marker changed'
w=w.replace(old,new,1)

# Rebalance conflicting pending SCALP ideas before creating an underfilled SWING book.
old="""  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=rawAnalyses.map(toStandbyCandidate).filter(Boolean).filter(x=>!activeSymbols.has(canonical(x.symbol))).sort(compareSetupPriority).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);let promotion=null,afterCreate=await realtimePortfolioSnapshot(env);if(Number(afterCreate.styles?.[style]||0)<styleTarget(style))promotion=await promoteCryptoStandby(env,style,'SCAN_IMMEDIATE_REFILL');await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,stable100Symbols:stable100.map(x=>x.symbol),liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,assessmentFailures,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),standby,promotion,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.19 stable-universe 15-slot engine: target 10 SCALP + 5 SWING. Full live universe is refreshed every maintenance cycle; weak-liquidity/high-spread/fragile candidates are excluded before deep analysis; strict signals are preferred and fresh conditional LIMIT/STOP reserves refill depleted slots.'};"""
new="""  const rebalance=style==='SWING'&&styleUnderfilled?await rebalanceCryptoStyle(env,style,analyses):null;
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=rawAnalyses.map(toStandbyCandidate).filter(Boolean).filter(x=>!activeSymbols.has(canonical(x.symbol))).sort(compareSetupPriority).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);let promotion=null,afterCreate=await realtimePortfolioSnapshot(env);if(Number(afterCreate.styles?.[style]||0)<styleTarget(style))promotion=await promoteCryptoStandby(env,style,'SCAN_IMMEDIATE_REFILL');await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,stable100Target:STABLE100_SIZE,stable100Count:stable100.length,stable100Symbols:stable100.map(x=>x.symbol),liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,assessmentFailures,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),rebalance,standby,promotion,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.22.6 balanced 15-slot engine: exact target 10 SCALP + 5 SWING across MARKET/LIMIT/STOP, globally unique symbols. SWING receives first allocation priority and may rebalance only conflicting SCALP PENDING ideas; OPEN trades are never migrated by style balancing.'};"""
assert old in w, 'scanCrypto creation marker changed'
w=w.replace(old,new,1)

# Global maintenance gives the scarce 5 SWING slots first, then fills the wider SCALP universe.
old="""async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SCALP','SWING']){
    const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'REFILL_TO_TARGET':'STABLE100_ROTATION_REFRESH'}`);
    await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
    if(Number(p.styles?.[style]||0)<target){await promoteCryptoStandby(env,style,'CONTINUOUS_STABLE100_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  await kickCryptoServerMonitor(env).catch(()=>{});return {mode:'STABLE100_CONTINUOUS',stableUniverse:await readStable100(env),attempted,portfolio:p,standbys:await cryptoStandbyStatus(env)};
}"""
new="""async function cryptoOnlyMaintenance(env){
  let p=await realtimePortfolioSnapshot(env),attempted=[];
  for(const style of ['SWING','SCALP']){
    const target=styleTarget(style),underfilled=Number(p.styles?.[style]||0)<target;attempted.push(`${style}:${underfilled?'REFILL_TO_TARGET':'STABLE100_ROTATION_REFRESH'}`);
    await scanCrypto(env,style).catch(()=>{});p=await realtimePortfolioSnapshot(env);
    if(Number(p.styles?.[style]||0)<target){await promoteCryptoStandby(env,style,'CONTINUOUS_STABLE100_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  }
  for(const style of ['SWING','SCALP'])if(Number(p.styles?.[style]||0)<styleTarget(style)){await scanCrypto(env,style).catch(()=>{});await promoteCryptoStandby(env,style,'SECOND_PASS_TARGET_REFILL').catch(()=>{});p=await realtimePortfolioSnapshot(env);}
  await kickCryptoServerMonitor(env).catch(()=>{});return {mode:'BALANCED_EXACT_10_SCALP_5_SWING',stableUniverse:await readStable100(env),attempted,portfolio:p,standbys:await cryptoStandbyStatus(env)};
}"""
assert old in w, 'maintenance marker changed'
w=w.replace(old,new,1)

# Release metadata explains the allocator behavior.
needle='  notes: [\n'
if 'V3.22.6 fixes style starvation' not in w:
    w=w.replace(needle,needle+"    'V3.22.6 fixes style starvation: SWING is allocated before SCALP, and an underfilled SWING book may reclaim only a conflicting SCALP PENDING idea. OPEN trades are never cancelled by style rebalancing.',\n    'V3.22.6 expands hot-spare depth and lets the 1-second lifecycle monitor refill any under-target style immediately from prepared safe LIMIT/STOP candidates while preserving global symbol uniqueness.',\n",1)

# Android/build identity only; V3.22.5 realtime transport implementation stays intact.
a=a.replace('APP_VERSION="3.22.5"','APP_VERSION="3.22.6"')
a=a.replace('SignalHub V3.22.5','SignalHub V3.22.6').replace('SignalHub 3.22.5','SignalHub 3.22.6')
c=c.replace('SignalHub-Android/3.22.5','SignalHub-Android/3.22.6')
m=m.replace('SignalHub V3.22.5','SignalHub V3.22.6')
g=g.replace('versionCode 34','versionCode 35').replace("versionName '3.22.5'","versionName '3.22.6'")

worker.write_text(w);activity.write_text(a);api.write_text(c);monitor.write_text(m);gradle.write_text(g)

assert 'SIGNALHUB-V3-GATEWAY-3.22.6' in w
assert 'rebalanceForStyle' in w and 'rebalanceCryptoStyle' in w
assert "for(const style of ['SWING','SCALP'])" in w
assert 'standbyPerStyle:40' in w
assert 'ONE_SECOND_TARGET_REFILL' in w
assert 'APP_VERSION="3.22.6"' in a
assert 'SignalHub-Android/3.22.6' in c
assert 'versionCode 35' in g and "versionName '3.22.6'" in g
print('patched SignalHub V3.22.6 balanced realtime book')
