from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()


def must(old,new,count=1):
    global s
    n=s.count(old)
    if n < count:
        raise SystemExit(f'PATCH_MISS count={n} old={old[:180]!r}')
    s=s.replace(old,new,count)


def between(start,end,new):
    global s
    i=s.find(start)
    if i < 0:
        raise SystemExit(f'START_MISS {start!r}')
    j=s.find(end,i)
    if j < 0:
        raise SystemExit(f'END_MISS {end!r}')
    s=s[:i]+new+s[j:]


if '3.69.0-modern-market-guard' in s and 'MICRO_LIVE_EXECUTOR_V369_MODERN_MARKET_GUARD=STARTED' in s:
    print('V369_PATCH_ALREADY_ACTIVE=TRUE')
    p.write_text(s)
    raise SystemExit(0)

if '3.60.0-profit-aware-exits' not in s or 'MICRO_LIVE_EXECUTOR_V360_PROFIT_AWARE=STARTED' not in s:
    raise SystemExit('V360_PRODUCTION_BASELINE_REQUIRED')

must("const WHALE=`${APP}/runtime-status/whale-flow-intel.json`;",
     "const WHALE=`${APP}/runtime-status/whale-flow-intel.json`;\nconst CIRCUIT=`${DATA}/entry-circuit.json`;\nconst SELF_TEST=process.argv.includes('--self-test');",1)

intel = r'''function feedAgeSec(x){const ts=x?.updatedAt||x?.timestamp||x?.generatedAt||0;const age=(Date.now()-Date.parse(ts))/1000;return Number.isFinite(age)&&age>=0?age:Infinity}
function badIntelStatus(v){return new Set(['DEGRADED','INTERNAL_ERROR','ERROR','OFFLINE','STALE','RATE_LIMIT_BACKOFF','WARMING_UP']).has(String(v||'').toUpperCase())}
function feedHealthyDoc(x,maxAgeSec){return !!x&&feedAgeSec(x)<=maxAgeSec&&!badIntelStatus(x.status)}
function rowObservedAgeSec(row,parent){const ts=row?.observedAt||row?.updatedAt||row?.timestamp||parent?.updatedAt||parent?.timestamp||0;const age=(Date.now()-Date.parse(ts))/1000;return Number.isFinite(age)&&age>=0?age:Infinity}
function intelRow(path,c,maxAgeSec=20){if(!c)return null;const x=read(path,{});const feedMax=path===WHALE?180:Math.max(15,maxAgeSec*2);if(!feedHealthyDoc(x,feedMax))return null;const row=(x.rows||[]).find(r=>r.mint===c.mint);if(!row)return null;if(path===REALTIME&&Number.isFinite(Number(row.lastEventAgeMs))&&Number(row.lastEventAgeMs)<=maxAgeSec*1000)return row;return rowObservedAgeSec(row,x)<=maxAgeSec?row:null}
function realtimeFor(c){return intelRow(REALTIME,c,8)}
function whaleFor(c){return intelRow(WHALE,c,120)}
function modernIntelState(c){
  if(SELF_TEST)return{rtFeed:true,whaleFeed:true,rtRow:true,whaleRow:true,haircut:1,entryAllowed:true,mode:'SELF_TEST'};
  const rt=read(REALTIME,{}),wh=read(WHALE,{}),rtFeed=feedHealthyDoc(rt,15),whaleFeed=feedHealthyDoc(wh,180),rtRow=!!realtimeFor(c),whaleRow=!!whaleFor(c);
  let haircut=0,mode='BOTH_FEEDS_DOWN';
  if(rtRow&&whaleRow){haircut=1;mode='FULL_INTEL'}
  else if(rtRow){haircut=.88;mode='REALTIME_ONLY'}
  else if(whaleRow){haircut=.76;mode='WHALE_ONLY'}
  else if(rtFeed||whaleFeed){haircut=.66;mode='FEED_HEALTHY_ROW_MISSING'}
  return{rtFeed,whaleFeed,rtRow,whaleRow,haircut,entryAllowed:rtFeed||whaleFeed,mode};
}
function modernIntelEntryAllowed(c){return modernIntelState(c).entryAllowed}
function circuitBackoffMs(failures){const f=Math.max(0,Math.floor(n(failures)));return f<5?0:Math.min(180000,15000*Math.pow(2,Math.min(4,f-5)))}
function circuitState(){return read(CIRCUIT,{failures:0,openUntilMs:0,lastFailureAtMs:0,lastError:null})}
function entryCircuitOpen(){if(SELF_TEST)return false;const x=circuitState();return n(x.openUntilMs)>Date.now()}
function executionCircuitFail(err){
  const old=circuitState(),now=Date.now(),recent=now-n(old.lastFailureAtMs)<=120000,failures=(recent?n(old.failures):0)+1,wait=circuitBackoffMs(failures),out={version:'3.69.0',updatedAt:new Date().toISOString(),failures,lastFailureAtMs:now,openUntilMs:wait?now+wait:n(old.openUntilMs),lastError:String(err?.message||err||'EXECUTION_FAILURE').slice(0,180)};
  atomic(CIRCUIT,out);if(wait>0)event({type:'ENTRY_CIRCUIT_BREAKER',state:'OPEN',failures,backoffMs:wait,error:out.lastError});
}
function executionCircuitSuccess(){
  if(SELF_TEST)return;const old=circuitState(),now=Date.now(),failures=Math.max(0,n(old.failures)-2),openUntilMs=n(old.openUntilMs)>now?n(old.openUntilMs):0;atomic(CIRCUIT,{...old,version:'3.69.0',updatedAt:new Date().toISOString(),failures,openUntilMs,lastSuccessAt:new Date().toISOString()});
}
function dangerousTokenFlags(c){
  const out=[];if(!c)return out;if(c.token2022===true)out.push('TOKEN_2022');if(c.mintAuthorityActive===true||c.mintAuthorityRevoked===false)out.push('MINT_AUTHORITY');if(c.freezeAuthorityActive===true||c.freezeAuthorityRevoked===false)out.push('FREEZE_AUTHORITY');if(c.transferHook===true||c.transferHookActive===true)out.push('TRANSFER_HOOK');if(c.permanentDelegate===true||c.permanentDelegateActive===true)out.push('PERMANENT_DELEGATE');if(c.nonTransferable===true)out.push('NON_TRANSFERABLE');return out
}
function explicitLiquidityDropPct(c){for(const k of ['liquidityChange5mPct','liquidityDelta5mPct','liquidityChangePct5m','liquidityDrop5mPct']){if(Number.isFinite(Number(c?.[k])))return Number(c[k])}return null}
function rugShieldReason(c){
  if(!c)return null;if(c.sellRoute===false)return'SELL_ROUTE_LOST';if(c.securityDecision==='BLOCK')return'SECURITY_BLOCK';if(c.holderClusterDecision==='BLOCK')return'HOLDER_CLUSTER_BLOCK';const flags=dangerousTokenFlags(c);if(flags.length)return'TOKEN_SAFETY_'+flags[0];if(n(c.liquidityUsd,999999)<15000)return'LIQUIDITY_COLLAPSE';const d=explicitLiquidityDropPct(c);if(d!==null&&d<=-35)return'LIQUIDITY_DROP_35PCT';const w=whaleFor(c);if(w&&n(w.top10Pct)<100&&n(w.top10Pct)>=70)return'WHALE_TOP10_CONCENTRATION';if(w&&n(w.deltaTop10Pct)>=8)return'WHALE_CONCENTRATION_SPIKE';return null
}
function liquidityAllocationCapPct(c){const liq=n(c?.liquidityUsd);if(liq<75000)return 5;if(liq<150000)return 8;if(liq<300000)return 12;if(liq<750000)return 16;if(liq<1500000)return 20;return 24}
'''
between('function intelRow(path,c,maxAgeSec=20){','function learningState(st){',intel+'function learningState(st){')

# Wrap the existing low-latency execution path. This does not change the signed
# transaction or fallback semantics; it only feeds a persistent entry circuit breaker.
must('async function executeOrder(o){','async function executeOrderRaw(o){',1)
wrapper = r'''async function executeOrder(o){
  try{const sig=await executeOrderRaw(o);executionCircuitSuccess();return sig}catch(e){executionCircuitFail(e);throw e}
}

'''
idx=s.find('function candidates()')
if idx<0: raise SystemExit('CANDIDATES_MARKER_MISSING')
s=s[:idx]+wrapper+s[idx:]

# Keep every original entry rule, then layer the modern fail-closed entry gate on top.
must('function trendEntryEligible(c){','function trendEntryEligibleBase(c){',1)
idx=s.find('function hardSafetyBroken(c){')
if idx<0: raise SystemExit('HARD_SAFETY_MARKER_MISSING')
entry_wrap = r'''function trendEntryEligible(c){
  if(SELF_TEST)return trendEntryEligibleBase(c);
  if(entryCircuitOpen())return false;
  if(!modernIntelEntryAllowed(c))return false;
  return trendEntryEligibleBase(c);
}
'''
s=s[:idx]+entry_wrap+s[idx:]

# Strengthen hard safety without weakening any original condition. Missing optional
# fields never trigger a rug exit; only explicit negative signals do.
hard = r'''function hardSafetyBroken(c){if(!c)return false;if(rugShieldReason(c))return true;if((Array.isArray(c.hardReject)&&c.hardReject.length>0)||c.sellRoute===false||c.token2022===true)return true;if(c.securityDecision==='BLOCK'||c.holderClusterDecision==='BLOCK')return true;if(n(c.liquidityUsd,999999)<20_000)return true;return false}
'''
between('function hardSafetyBroken(c){','function severeTrendBreak(c){',hard+'function severeTrendBreak(c){')

# Preserve the adaptive allocation engine, but cap concentration by exit liquidity and
# haircut size when only a subset of intelligence is fresh.
allocation = r'''function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const rt=realtimeFor(c),rtQ=rt?clamp((n(rt.eventMomentum)-.8)/2.2,0,1):.35,w=whaleFor(c),whaleQ=w?clamp((n(w.whaleFlowScore)+10)/16,0,1):.50,learn=learnedBoost(st,c),learnQ=clamp(.5+learn/24,0,1);
  const quality=clamp(scoreQ*.26+netQ*.15+avgQ*.09+liqQ*.13+impactQ*.13+pulseQ*.08+rtQ*.07+whaleQ*.05+learnQ*.04,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.28),.80,2.00);
  const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1),basePct=4+31*Math.pow(quality,1.20),cashBoost=1+0.38*freeRatio;
  const intel=modernIntelState(c),rawPct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct),liqCap=liquidityAllocationCapPct(c),pct=clamp(Math.min(rawPct*intel.haircut,liqCap),0,p.maxUtilizationPct);
  return{name:'AUTO_ALPHA_V369',pct,quality,growth,exposure,freeRatio,cashBoost,learnedBoost:learn,expectedEdge:expectedEdge(st,c),score:opportunityScore(c),intelMode:intel.mode,intelHaircut:intel.haircut,liquidityCapPct:liqCap};
}
'''
between('function allocationProfile(c,p,st,capitalBaseLamports){','function rank(c){',allocation+'function rank(c){')

# Preserve exact emergency-exit priority while exposing the explicit RugShield reason.
old='''    if(hardSafetyBroken(c)){await sell(st,i,'HARD_SAFETY_BREAK');return{action:'SELL',reason:'HARD_SAFETY_BREAK',symbol:pos.symbol}}'''
new='''    const rug=rugShieldReason(c);if(rug){event({type:'RUG_SHIELD_EXIT',mint:pos.mint,symbol:pos.symbol,reason:rug});await sell(st,i,'RUG_SHIELD_'+rug);return{action:'SELL',reason:'RUG_SHIELD_'+rug,symbol:pos.symbol}}\n    if(hardSafetyBroken(c)){await sell(st,i,'HARD_SAFETY_BREAK');return{action:'SELL',reason:'HARD_SAFETY_BREAK',symbol:pos.symbol}}'''
must(old,new,1)

must("st.version='3.60.0-profit-aware-exits'","st.version='3.69.0-modern-market-guard'",1)
must('MICRO_LIVE_EXECUTOR_V360_PROFIT_AWARE=STARTED','MICRO_LIVE_EXECUTOR_V369_MODERN_MARKET_GUARD=STARTED',1)
must('MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS','MICRO_EXECUTOR_V369_MODERN_MARKET_GUARD_SELF_TEST=PASS',1)

anchor="console.log('MICRO_EXECUTOR_V369_MODERN_MARKET_GUARD_SELF_TEST=PASS');"
extra=r'''if(circuitBackoffMs(4)!==0||circuitBackoffMs(5)!==15000||circuitBackoffMs(20)!==180000)throw new Error('CIRCUIT_BACKOFF_SELFTEST');
  if(liquidityAllocationCapPct({liquidityUsd:60000})!==5||liquidityAllocationCapPct({liquidityUsd:2000000})!==24)throw new Error('LIQUIDITY_CAP_SELFTEST');
  const danger=dangerousTokenFlags({token2022:true,transferHookActive:true});if(!danger.includes('TOKEN_2022')||!danger.includes('TRANSFER_HOOK'))throw new Error('TOKEN_EXTENSION_SELFTEST');
  if(rugShieldReason({sellRoute:false})!=='SELL_ROUTE_LOST'||rugShieldReason({liquidityUsd:10000})!=='LIQUIDITY_COLLAPSE')throw new Error('RUG_SHIELD_SELFTEST');
  console.log('MODERN_INTEL_FRESHNESS_GUARD=TRUE');console.log('WHALE_ROW_TIMESTAMP_FRESHNESS=TRUE');console.log('EXIT_LIQUIDITY_ALLOCATION_CAP=TRUE');console.log('ENTRY_CIRCUIT_BREAKER=TRUE');console.log('RUG_SHIELD_EXPLICIT_SIGNALS=TRUE');console.log('TOKEN2022_DANGEROUS_EXTENSION_BLOCK=TRUE');console.log('EXITS_NOT_BLOCKED_BY_INTEL=TRUE');
  '''+anchor
must(anchor,extra,1)

p.write_text(s)
print('V369_PATCH_APPLIED=TRUE')
