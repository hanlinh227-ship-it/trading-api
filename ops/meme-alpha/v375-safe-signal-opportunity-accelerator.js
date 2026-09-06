import fs from 'node:fs';

const P='/var/lib/meme-alpha/data/paper';
const OUT='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';
const REALTIME='/opt/meme-alpha/app/runtime-status/realtime-pool-pulse.json';
const WHALE='/opt/meme-alpha/app/runtime-status/whale-flow-intel.json';
const SELF_TEST=process.argv.includes('--self-test');
const VERSION='3.75.0-opportunity-accelerator';

const readFile=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const read=(n,d={})=>readFile(`${P}/${n}`,d);
const num=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const ageSec=(ts)=>{const t=Date.parse(ts||0);return Number.isFinite(t)?Math.max(0,(Date.now()-t)/1000):Infinity};
const badStatus=(s)=>new Set(['DEGRADED','INTERNAL_ERROR','ERROR','OFFLINE','STALE','RATE_LIMIT_BACKOFF','WARMING_UP','NO_RPC_CONFIG']).has(String(s||'').toUpperCase());
const feedHealthy=(x,maxAge)=>!!x&&!badStatus(x.status)&&ageSec(x.updatedAt||x.timestamp||x.generatedAt)<=maxAge;
const rowAgeSec=(r,parent)=>ageSec(r?.observedAt||r?.updatedAt||r?.timestamp||parent?.updatedAt||parent?.timestamp||parent?.generatedAt);

function freshRow(doc,mint,maxAge,kind){
  const r=(doc?.rows||[]).find(x=>x?.mint===mint);
  if(!r)return null;
  if(kind==='realtime'){
    if(r.lastEventAgeMs===null||r.lastEventAgeMs===undefined||r.lastEventAgeMs==='')return null;
    const eventAge=Number(r.lastEventAgeMs);
    return Number.isFinite(eventAge)&&eventAge>=0&&eventAge<=maxAge*1000?r:null;
  }
  return rowAgeSec(r,doc)<=maxAge?r:null;
}
function intelState(c,rt,wh){
  const rtFeed=feedHealthy(rt,15),whaleFeed=feedHealthy(wh,180);
  const rr=rtFeed?freshRow(rt,c.mint,8,'realtime'):null;
  const wr=whaleFeed?freshRow(wh,c.mint,120,'whale'):null;
  let mode='BOTH_FEEDS_DOWN',haircut=0;
  if(rr&&wr){mode='FULL_INTEL';haircut=1}
  else if(rr){mode='REALTIME_ONLY';haircut=.90}
  else if(wr){mode='WHALE_ONLY';haircut=.78}
  else if(rtFeed||whaleFeed){mode='FEED_HEALTHY_ROW_MISSING';haircut=.68}
  return {mode,haircut,entryAllowed:rtFeed||whaleFeed,rtFeed,whaleFeed,rtRow:rr,whaleRow:wr};
}
function explicitLiquidityDropPct(c){
  for(const k of ['liquidityChange5mPct','liquidityDelta5mPct','liquidityChangePct5m','liquidityDrop5mPct'])if(Number.isFinite(Number(c?.[k])))return Number(c[k]);
  return null;
}
function promotionCheck(c,intel,p,hardReject,securityDecision){
  const rr=intel.rtRow;
  const originalScore=num(c.score);
  const chg=Number.isFinite(Number(c.priceChange5m))?Number(c.priceChange5m):null;
  const net=num(c.netBuyers5m);
  const buyVol=num(c.buyVolume5m),sellVol=num(c.sellVolume5m),bs=sellVol>0?buyVol/sellVol:(buyVol>0?99:0);
  const liq=num(c.liquidityUsd);
  const consecutive=num(p?.consecutiveEligible);
  const fastTrack=!!p?.metrics?.fastTrackReady;
  const realtimeBurst=!!rr&&num(rr.events5s)>=2&&num(rr.eventMomentum)>=1.15&&num(rr.lastEventAgeMs,99999)<=2500;
  const conditions={
    watchLike:['WATCH','PERSISTENCE_WAIT','FAST_WATCH'].includes(String(c.decision||'')),
    noHardReject:hardReject.length===0,
    securityOk:securityDecision!=='BLOCK',
    sellRoute:c.sellRoute===true,
    liquidityOk:liq>=75000,
    scoreOk:originalScore>=50,
    buyersOk:net>=8,
    momentumOk:chg!==null&&chg>=0.15&&chg<=12,
    flowOk:bs>=1.12,
    intelOk:intel.entryAllowed&&(intel.mode==='FULL_INTEL'||intel.mode==='REALTIME_ONLY'),
    confirmationOk:consecutive>=1||fastTrack||realtimeBurst
  };
  const eligible=Object.values(conditions).every(Boolean);
  let mode=null;if(eligible)mode=consecutive>=1?'PERSISTENCE_CONFIRMED':fastTrack?'FAST_TRACK':'REALTIME_BURST';
  return {eligible,mode,conditions,realtimeBurst,events5s:num(rr?.events5s),eventMomentum:num(rr?.eventMomentum),lastEventAgeMs:rr?.lastEventAgeMs??null};
}
function guardCandidate(c,rt,wh){
  const intel=intelState(c,rt,wh);
  const p=globalThis.__persistFind?.(c.mint)||null;
  const hardReject=Array.isArray(c.hardReject)?[...c.hardReject]:[];
  const entryGuardReasons=[];
  const block=(reason)=>{if(!hardReject.includes(reason))hardReject.push(reason)};

  // Preserve hard safety. Token-2022 remains blocked unless a later audited release explicitly proves safe extensions.
  if(c.token2022===true)block('V369_TOKEN2022_DANGEROUS');
  if(c.mintAuthorityDisabled===false)block('V369_MINT_AUTHORITY_ACTIVE');
  if(c.freezeAuthorityDisabled===false)block('V369_FREEZE_AUTHORITY_ACTIVE');
  if(c.transferHook===true||c.transferHookActive===true)block('V369_TRANSFER_HOOK_ACTIVE');
  if(c.permanentDelegate===true||c.permanentDelegateActive===true)block('V369_PERMANENT_DELEGATE_ACTIVE');
  if(c.nonTransferable===true)block('V369_NON_TRANSFERABLE');
  if(num(c.liquidityUsd,999999)<15000)block('V369_LIQUIDITY_COLLAPSE');
  const liqDrop=explicitLiquidityDropPct(c);
  if(liqDrop!==null&&liqDrop<=-35)block('V369_LIQUIDITY_DROP_35PCT');
  if(intel.whaleRow&&num(intel.whaleRow.top10Pct,-1)>=70&&num(intel.whaleRow.top10Pct,-1)<100)block('V369_WHALE_TOP10_CONCENTRATION');
  if(intel.whaleRow&&num(intel.whaleRow.deltaTop10Pct,0)>=8)block('V369_WHALE_CONCENTRATION_SPIKE');

  let decision=c.decision;
  let securityDecision=hardReject.some(x=>String(x).startsWith('V369_'))?'BLOCK':c.securityDecision;
  if(!intel.entryAllowed){entryGuardReasons.push('V369_BOTH_INTEL_FEEDS_DOWN');if(decision==='PROBE_CANDIDATE')decision='INTEL_DEGRADED'}
  if(c.needsExtensionAudit===true&&decision==='PROBE_CANDIDATE'){entryGuardReasons.push('V369_EXTENSION_AUDIT_REQUIRED');decision='EXTENSION_AUDIT_REQUIRED'}

  const promotion=promotionCheck(c,intel,p,hardReject,securityDecision);
  let effectiveConsecutive=num(p?.consecutiveEligible);
  if(promotion.eligible&&decision!=='PROBE_CANDIDATE'){
    decision='PROBE_CANDIDATE';
    effectiveConsecutive=Math.max(1,effectiveConsecutive);
    entryGuardReasons.push(`V375_PROMOTED_${promotion.mode}`);
  }

  const originalScore=num(c.score);
  const score=intel.entryAllowed?Number((originalScore*intel.haircut).toFixed(4)):0;
  return {
    mint:c.mint,symbol:c.symbol,name:c.name,score,originalScore,decision,
    universeClass:c.universeClass,universeConfidence:c.universeConfidence,
    securityDecision,holderClusterDecision:c.holderClusterAudit?.decision||c.holderClusterDecision||null,
    devIdentityProven:c.holderClusterAudit?.devIdentityProven===true,holderClusterMaxAccountsSameOwner:num(c.holderClusterAudit?.maxAccountsSameOwner),
    hardReject,entryGuardReasons,token2022:!!c.token2022,pairAddress:c.pairAddress||null,
    sellRoute:c.sellRoute===true?true:(c.sellRoute===false?false:null),liquidityUsd:num(c.liquidityUsd),
    sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):null,sellQuoteHttp:c.sellQuoteHttp??null,sellQuoteError:c.sellQuoteError??null,
    sellImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):(Number.isFinite(Number(c.sellImpactPct))?Number(c.sellImpactPct):(Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null)),
    priceImpactPct:Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null,
    organicRatio5m:num(c.organicRatio5m),netBuyers5m:num(c.netBuyers5m),priceChange5m:Number.isFinite(Number(c.priceChange5m))?Number(c.priceChange5m):null,
    buyVolume5m:num(c.buyVolume5m),sellVolume5m:num(c.sellVolume5m),dexVolume5m:num(c.dexVolume5m),dexBuys5m:num(c.dexBuys5m),dexSells5m:num(c.dexSells5m),
    buySellRatio5m:num(c.sellVolume5m)>0?num(c.buyVolume5m)/num(c.sellVolume5m):num(c.buyVolume5m)>0?99:0,sources:c.sources||[],
    persistenceDecision:p?.persistenceDecision||null,consecutiveEligible:effectiveConsecutive,fastTrackReady:!!p?.metrics?.fastTrackReady,
    avgScoreLast2:p?.metrics?.avgScoreLast2??null,avgNetBuyersLast2:p?.metrics?.avgNetBuyersLast2??null,scoreSlopeLast2:p?.metrics?.scoreSlopeLast2??null,liquidityStableLast2:p?.metrics?.liquidityStableLast2??null,
    holderAuditDecision:c.holderClusterAudit?.decision||null,holderReviewReasons:c.holderClusterAudit?.reviewReasons||[],holderBlockReasons:c.holderClusterAudit?.blockReasons||[],holderEvidence:c.holderClusterAudit?.evidence||[],
    securityReviewReasons:c.securityReviewReasons||[],securityBlockReasons:c.securityBlockReasons||[],securityEvidence:c.securityEvidence||[],
    mintAuthorityDisabled:c.mintAuthorityDisabled,freezeAuthorityDisabled:c.freezeAuthorityDisabled,topHoldersPct:c.topHoldersPct??null,dexLiquidityUsd:c.dexLiquidityUsd??null,needsExtensionAudit:!!c.needsExtensionAudit,
    transferHookActive:c.transferHookActive===true||c.transferHook===true,permanentDelegateActive:c.permanentDelegateActive===true||c.permanentDelegate===true,nonTransferable:c.nonTransferable===true,
    liquidityChange5mPct:liqDrop,intelMode:intel.mode,intelHaircut:intel.haircut,realtimeFeedFresh:intel.rtFeed,whaleFeedFresh:intel.whaleFeed,realtimeRowFresh:!!intel.rtRow,whaleRowFresh:!!intel.whaleRow,
    whaleTop10Pct:intel.whaleRow?.top10Pct??null,whaleDeltaTop10Pct:intel.whaleRow?.deltaTop10Pct??null,
    opportunityAcceleration:{eligible:promotion.eligible,mode:promotion.mode,conditions:promotion.conditions,events5s:promotion.events5s,eventMomentum:promotion.eventMomentum,lastEventAgeMs:promotion.lastEventAgeMs}
  };
}

if(SELF_TEST){
  const now=new Date().toISOString();
  const rt={status:'HEALTHY',updatedAt:now,rows:[{mint:'SAFE',lastEventAgeMs:400,events5s:4,eventMomentum:1.8},{mint:'BAD',lastEventAgeMs:300,events5s:5,eventMomentum:2}]};
  const wh={status:'HEALTHY',updatedAt:now,rows:[]};
  globalThis.__persistFind=(m)=>({consecutiveEligible:0,metrics:{fastTrackReady:false}});
  const safe=guardCandidate({mint:'SAFE',score:62,decision:'WATCH',securityDecision:'ALLOW',sellRoute:true,liquidityUsd:250000,netBuyers5m:20,priceChange5m:2,buyVolume5m:200,sellVolume5m:100,token2022:false,mintAuthorityDisabled:true,freezeAuthorityDisabled:true},rt,wh);
  if(safe.decision!=='PROBE_CANDIDATE'||safe.consecutiveEligible<1||safe.opportunityAcceleration.mode!=='REALTIME_BURST')throw new Error('REALTIME_PROMOTION_SELFTEST');
  const bad=guardCandidate({mint:'BAD',score:80,decision:'WATCH',securityDecision:'ALLOW',sellRoute:true,liquidityUsd:500000,netBuyers5m:30,priceChange5m:3,buyVolume5m:300,sellVolume5m:100,token2022:true,mintAuthorityDisabled:true,freezeAuthorityDisabled:true},rt,wh);
  if(bad.decision==='PROBE_CANDIDATE'||!bad.hardReject.includes('V369_TOKEN2022_DANGEROUS'))throw new Error('HARD_GUARD_BYPASS_SELFTEST');
  const down=guardCandidate({mint:'X',score:90,decision:'PROBE_CANDIDATE',securityDecision:'ALLOW',sellRoute:true,liquidityUsd:500000}, {}, {});
  if(down.decision==='PROBE_CANDIDATE')throw new Error('BOTH_FEEDS_DOWN_LEAK_SELFTEST');
  console.log('V375_OPPORTUNITY_ACCELERATOR_SELF_TEST=PASS');
  console.log('REALTIME_BURST_PROMOTION=TRUE');
  console.log('HARD_GUARDS_PRESERVED=TRUE');
  console.log('SELL_ROUTE_REQUIRED=TRUE');
  console.log('BOTH_FEEDS_DOWN_FAIL_CLOSED=TRUE');
  process.exit(0);
}

const scan=read('scanner-latest.json',{candidates:[]});
const persist=read('persistence-state.json');
const risk=read('risk-state.json');
const source=read('scanner-source-health.json');
const realtime=readFile(REALTIME,{});
const whale=readFile(WHALE,{});
function findP(m){for(const root of [persist.tokens,persist.candidates,persist.state,persist]){if(!root)continue;if(Array.isArray(root)){const x=root.find(v=>v?.mint===m);if(x)return x}else if(typeof root==='object'&&root[m])return root[m]}return null}
globalThis.__persistFind=findP;

const candidates=(scan.candidates||[]).map(c=>{
  const g=guardCandidate(c,realtime,whale);
  if(source?.allowNewEntries===false&&g.decision==='PROBE_CANDIDATE'){
    g.decision='SOURCE_HEALTH_BLOCK';g.entryGuardReasons.push('V369_SOURCE_HEALTH_BLOCK');
  }
  return g;
}).sort((a,b)=>b.score-a.score).slice(0,40);
const safeRisk={};for(const k of Object.keys(risk||{})){const v=risk[k];if(['string','number','boolean'].includes(typeof v)||v===null)safeRisk[k]=v;else if(Array.isArray(v))safeRisk[k]=v.slice(0,10);else if(v&&typeof v==='object'&&JSON.stringify(v).length<12000)safeRisk[k]=v}
const sourceHealth={status:source?.status||null,checkedAt:source?.checkedAt||null,successfulSources:num(source?.successfulSources),failedSources:num(source?.failedSources),usingCache:source?.usingCache===true,allowNewEntries:source?.allowNewEntries===true};
const summary={
  fullIntel:candidates.filter(x=>x.intelMode==='FULL_INTEL').length,realtimeOnly:candidates.filter(x=>x.intelMode==='REALTIME_ONLY').length,whaleOnly:candidates.filter(x=>x.intelMode==='WHALE_ONLY').length,
  feedHealthyRowMissing:candidates.filter(x=>x.intelMode==='FEED_HEALTHY_ROW_MISSING').length,bothFeedsDown:candidates.filter(x=>x.intelMode==='BOTH_FEEDS_DOWN').length,
  blockedByModernGuard:candidates.filter(x=>x.hardReject.some(r=>String(r).startsWith('V369_'))).length,sourceHealthBlocked:candidates.filter(x=>x.entryGuardReasons.includes('V369_SOURCE_HEALTH_BLOCK')).length,
  promotedRealtimeBurst:candidates.filter(x=>x.opportunityAcceleration?.mode==='REALTIME_BURST'&&x.decision==='PROBE_CANDIDATE').length,
  promotedFastTrack:candidates.filter(x=>x.opportunityAcceleration?.mode==='FAST_TRACK'&&x.decision==='PROBE_CANDIDATE').length,
  promotedPersistence:candidates.filter(x=>x.opportunityAcceleration?.mode==='PERSISTENCE_CONFIRMED'&&x.decision==='PROBE_CANDIDATE').length,
  probeCandidates:candidates.filter(x=>x.decision==='PROBE_CANDIDATE').length
};
const nowIso=new Date().toISOString();
const out={version:VERSION,trendTelemetryRevision:'2.6.1',timestamp:nowIso,updatedAt:nowIso,scannerVersion:scan.version||null,sourceHealth,risk:safeRisk,intelSummary:summary,candidates};
const t=OUT+'.tmp';fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,OUT);try{fs.chmodSync(OUT,0o664)}catch{}
console.log(`SAFE_SIGNAL_EXPORT=${candidates.length} SOURCE=${sourceHealth.status} V375_INTEL=${JSON.stringify(summary)}`);
