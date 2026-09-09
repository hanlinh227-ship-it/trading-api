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

rep("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.15.1';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.15.2';",'version')
rep("replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC'","replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL'",'top replacement mode')
rep("replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC'","replacementMode:'DURABLE_OBJECT_HOT_SPARE_ATOMIC_RESERVE_POOL'",'runtime replacement mode')

old_set=r'''  async setStandbys(payload){
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
'''
new_set=r'''  async setStandbys(payload){
    const style=String(payload?.style||'').toUpperCase();if(!['SCALP','SWING'].includes(style))return {ok:false,error:'BAD_STYLE'};
    const key=`standby:${style}`,old=(await this.state.storage.get(key))||{rows:[]},reg=await this.registry(),active=this.activeRows(reg),activeSymbols=new Set(active.map(x=>canonical(x.symbol))),rows=[],seen=new Set(),incoming=Array.isArray(payload?.signals)?payload.signals:[];
    const combined=[...incoming,...(Array.isArray(old.rows)?old.rows:[])];
    for(const raw of combined){
      if(rows.length>=Number(PORTFOLIO_POLICY.standbyPerStyle||3))break;
      const s={...(raw||{})},symbol=canonical(s.symbol),order=String(s.orderType||'').toUpperCase();
      if(!symbol||seen.has(symbol)||activeSymbols.has(symbol))continue;
      if(String(s.market||'CRYPTO').toUpperCase()!=='CRYPTO'||String(s.style||style).toUpperCase()!==style)continue;
      if(!['LIMIT','STOP'].includes(order)||!validSignalStructure(s))continue;
      const assessment=assessCoverageSetup(s);if(assessment?.verdict!=='PASS')continue;
      rows.push({...s,market:'CRYPTO',style,status:'PENDING',entryState:'PENDING_ENTRY',coverageFallback:true,coverageTier:s.coverageTier||'HOT_SPARE_CONDITIONAL',entryAssessment:assessment,engineVersion:V3_VERSION,checkpoint:CHECKPOINT,standbyPreparedAt:s.standbyPreparedAt||nowIso()});seen.add(symbol);
    }
    const pack={style,preparedAt:Date.now(),receivedAt:nowIso(),rows};await this.state.storage.put(key,pack);return {ok:true,style,count:rows.length,symbols:rows.map(x=>x.symbol)};
  }
'''
rep(old_set,new_set,'merge-preserve standby pool')

standby_fn=r'''function toStandbyCandidate(raw){
  if(!raw)return null;const s={...raw,technicalAtIssue:{...(raw.technicalAtIssue||{})},qualityEvidence:{...(raw.qualityEvidence||{})}},style=String(s.style||'SCALP').toUpperCase(),dir=['LONG','BUY'].includes(String(s.side||'').toUpperCase())?1:-1,src=Number(s.sourcePrice||s.lastPrice||0);if(!(src>0))return null;
  let entry=Number(s.entry||src),sl=Number(s.sl||0),risk=Math.abs(entry-sl),order=String(s.orderType||'').toUpperCase();if(!(risk>0))return null;
  if(!['LIMIT','STOP'].includes(order)){
    const spreadPx=Math.max(0,src*Number(s.technicalAtIssue?.spreadBps||0)/10000),offset=Math.max(risk*(style==='SWING'?.16:.11),spreadPx*2.5);
    order='STOP';entry=src+dir*offset;
    if((dir>0&&!(sl<entry))||(dir<0&&!(sl>entry)))sl=entry-dir*risk;
    risk=Math.abs(entry-sl);if(!(risk>0))return null;
    const minRR=style==='SWING'?2.85:2.20;
    s.tp1=entry+dir*risk*.92;s.tp2=entry+dir*risk*1.58;s.tp3=entry+dir*risk*minRR;s.tp=s.tp3;s.targetRR=minRR;s.entryModel='HOT_SPARE_CONFIRMATION_STOP';
  }
  s.orderType=order;s.entry=entry;s.sl=sl;s.status='PENDING';s.entryState='PENDING_ENTRY';s.lifecycle='PENDING_ENTRY';s.coverageFallback=true;s.coverageTier='HOT_SPARE_CONDITIONAL';s.standbySource='DERIVED_FROM_CURRENT_ANALYSIS';s.qualityEvidence.coverageConditional=true;
  if(!Number.isFinite(Number(s.invalidationLevel))||Number(s.invalidationLevel)<=0)s.invalidationLevel=sl;
  const a=assessCoverageSetup(s);if(a.verdict!=='PASS')return null;s.entryAssessment=a;return s;
}
'''
insert_before('function setupPriority(s){',standby_fn,'standby derivation')

old_scan="""  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=analyses.filter(x=>!activeSymbols.has(canonical(x.symbol))&&['LIMIT','STOP'].includes(String(x.orderType||'').toUpperCase())).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),standby,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.15.1 fixed 2x2 book with hot spares: strict setups are preferred; conditional LIMIT/STOP coverage remains hard-safety checked, and the Durable Object promotes a prepared spare immediately after TP/SL/cancellation when possible.'};
"""
new_scan="""  const created=await maybeCreateV31(env,'CRYPTO',style,analyses),activeBook=await getActiveBook(env),activeSymbols=new Set(activeBook.map(x=>canonical(x.symbol))),standbyCandidates=rawAnalyses.map(toStandbyCandidate).filter(Boolean).filter(x=>!activeSymbols.has(canonical(x.symbol))).sort(compareSetupPriority).slice(0,PORTFOLIO_POLICY.standbyPerStyle),standby=await setCryptoStandbys(env,style,standbyCandidates);let promotion=null,afterCreate=await realtimePortfolioSnapshot(env);if(Number(afterCreate.styles?.[style]||0)<PORTFOLIO_POLICY.targetActivePerStyle)promotion=await promoteCryptoStandby(env,style,'SCAN_IMMEDIATE_REFILL');await kickCryptoServerMonitor(env).catch(()=>{});
  return {ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',market:'CRYPTO',style,provider:snap.provider,live:true,scanned:all.length,liquidUniverse:liquid.length,deepAnalyzed:ranked.length,evaluated:rawAnalyses.length,actionable:analyses.length,rejectedByAssessment:rawAnalyses.length-analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,portfolioBlocked:Math.max(0,analyses.length-created.length),standby,promotion,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),portfolioPolicy:PORTFOLIO_POLICY,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'V3.15.2 fixed 2x2 reserve-pool engine: strict signals are preferred; every scan also derives hard-safety checked conditional pending reserves from the broader live analysis set, preserves prior valid reserves, and atomically promotes a reserve whenever a style drops below two.'};
"""
rep(old_scan,new_scan,'robust standby generation')

rep("V315R-CRYPTO-${style}-${symbol}","V3152R-CRYPTO-${style}-${symbol}",'replacement id')

cp=Path('SIGNALHUB_V3_CHECKPOINT_07_FIXED_2X2.md')
if cp.exists():
    cp.write_text(cp.read_text()+"""\n## V3.15.2 reserve-pool hardening\n- Standby pools merge and preserve still-valid reserves instead of being erased by an empty scan.\n- Any current analyzed setup can be converted into a conditional confirmation STOP reserve when it is not already a pending order.\n- Derived reserves are rechecked by V315_FIXED_2X2_HARD_SAFETY before storage or promotion.\n- Scanner immediately promotes a reserve after analysis if its style remains under the 2-active target.\n- Active signals remain capped at exactly 2 SCALP + 2 SWING; reserve signals are hidden until promotion.\n""")
P.write_text(s)
print('patched SignalHub V3.15.2 robust reserve pool')
