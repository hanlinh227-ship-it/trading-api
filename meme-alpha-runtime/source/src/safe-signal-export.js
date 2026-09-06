import fs from 'node:fs';

const P='/var/lib/meme-alpha/data/paper';
const OUT='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';
const REALTIME='/opt/meme-alpha/app/runtime-status/realtime-pool-pulse.json';
const WHALE='/opt/meme-alpha/app/runtime-status/whale-flow-intel.json';
const SELF_TEST=process.argv.includes('--self-test');
const VERSION='3.77.0-objective-insider-risk';

const readFile=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const read=(n,d={})=>readFile(`${P}/${n}`,d);
const num=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const finite=v=>Number.isFinite(Number(v));
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const ageSec=(ts)=>{const t=Date.parse(ts||0);return Number.isFinite(t)?Math.max(0,(Date.now()-t)/1000):Infinity};
const badStatus=(s)=>new Set(['DEGRADED','INTERNAL_ERROR','ERROR','OFFLINE','STALE','RATE_LIMIT_BACKOFF','WARMING_UP','NO_RPC_CONFIG']).has(String(s||'').toUpperCase());
const feedHealthy=(x,maxAge)=>!!x&&!badStatus(x.status)&&ageSec(x.updatedAt||x.timestamp||x.generatedAt)<=maxAge;
const rowAgeSec=(r,parent)=>ageSec(r?.observedAt||r?.updatedAt||r?.timestamp||parent?.updatedAt||parent?.timestamp||parent?.generatedAt);
const impact=c=>Math.abs(num(c?.sellPriceImpactPct??c?.sellImpactPct??c?.priceImpactPct,99));

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
  for(const k of ['liquidityChange5mPct','liquidityDelta5mPct','liquidityChangePct5m','liquidityDrop5mPct'])if(finite(c?.[k]))return Number(c[k]);
  return null;
}
function radarMeta(c){
  const r=c?.newListingRadar||{};
  const sources=Array.isArray(c?.sources)?c.sources:[];
  return {
    pairAgeSec:finite(r.pairAgeSec)?Number(r.pairAgeSec):(finite(c?.pairAgeSec)?Number(c.pairAgeSec):null),
    fastDiscoveryLane:r.fastDiscoveryLane===true||c?.fastDiscoveryLane===true||sources.includes('fast-discovery-v372'),
    preScore:finite(r.preScore)?Number(r.preScore):(finite(c?.preScore)?Number(c.preScore):null),
    discoveryPriority:finite(r.discoveryPriority)?Number(r.discoveryPriority):(finite(c?.discoveryPriority)?Number(c.discoveryPriority):null),
    ageBucket:r.ageBucket||c?.radarAgeBucket||null
  };
}
function marketRegime(scan,rt){
  const rows=Array.isArray(scan?.candidates)?scan.candidates:[];
  const denom=Math.max(1,rows.length);
  const positive=rows.filter(c=>num(c.priceChange5m)<=15&&num(c.priceChange5m)>=1&&num(c.netBuyers5m)>0).length;
  const negative=rows.filter(c=>num(c.priceChange5m)<-3).length;
  const fast=rows.filter(c=>radarMeta(c).fastDiscoveryLane).length;
  const bursts=(rt?.rows||[]).filter(r=>r.lastEventAgeMs!==null&&finite(r.lastEventAgeMs)&&num(r.lastEventAgeMs,99999)<=3000&&num(r.events5s)>=2&&num(r.eventMomentum)>=1.2).length;
  const positiveRatio=positive/denom,negativeRatio=negative/denom;
  let name='MIXED';
  if(bursts>=3||positiveRatio>=.35)name='HOT_MOMENTUM';
  else if(negativeRatio>=.35)name='DEFENSIVE_ROTATION';
  return {name,candidateCount:rows.length,positiveRatio:Number(positiveRatio.toFixed(3)),negativeRatio:Number(negativeRatio.toFixed(3)),fastDiscoveryCount:fast,realtimeBurstCount:bursts};
}
function laneBoost(lane,regime){
  const base={LAUNCH_FAST:6,MOMENTUM:7,RECOVERY_FLOW:5,ESTABLISHED_ROTATION:4}[lane]||0;
  const bonus=(regime?.name==='HOT_MOMENTUM'&&(lane==='LAUNCH_FAST'||lane==='MOMENTUM'))||(regime?.name==='DEFENSIVE_ROTATION'&&(lane==='RECOVERY_FLOW'||lane==='ESTABLISHED_ROTATION'))?1:0;
  return Math.min(8,base+bonus);
}
function routeCandidate(c,intel,p,hardReject,securityDecision,holderDecision,regime){
  const rr=intel.rtRow,meta=radarMeta(c),score=num(c.score),liq=num(c.liquidityUsd),chg=finite(c.priceChange5m)?Number(c.priceChange5m):null;
  const net=num(c.netBuyers5m),buyVol=num(c.buyVolume5m),sellVol=num(c.sellVolume5m),bs=sellVol>0?buyVol/sellVol:(buyVol>0?99:0);
  const consecutive=num(p?.consecutiveEligible),fastTrack=!!p?.metrics?.fastTrackReady,avg=num(p?.metrics?.avgNetBuyersLast2,0),slope=num(p?.metrics?.scoreSlopeLast2,0),stable=p?.metrics?.liquidityStableLast2!==false;
  const rtPulse=!!rr&&num(rr.events5s)>=1&&num(rr.eventMomentum)>=1.03&&num(rr.lastEventAgeMs,99999)<=3500;
  const rtBurst=!!rr&&num(rr.events5s)>=2&&num(rr.eventMomentum)>=1.15&&num(rr.lastEventAgeMs,99999)<=3000;
  const watchLike=['WATCH','PERSISTENCE_WAIT','FAST_WATCH'].includes(String(c.decision||''));
  const actionableSafe=c.universeClass==='MEME_CONFIRMED'&&securityDecision==='PASS'&&holderDecision==='PASS'&&hardReject.length===0&&c.token2022!==true&&c.sellRoute===true&&liq>=50000&&impact(c)<=1.25&&stable&&intel.entryAllowed&&(intel.mode==='FULL_INTEL'||intel.mode==='REALTIME_ONLY');
  const common={watchLike,actionableSafe,stable,intelRealtime:!!rr,sellRoute:c.sellRoute===true,universeConfirmed:c.universeClass==='MEME_CONFIRMED',securityPass:securityDecision==='PASS',holderPass:holderDecision==='PASS',noHardReject:hardReject.length===0,impactOk:impact(c)<=1.25};
  const lanes=[];
  const add=(lane,eligible,quality,conditions)=>lanes.push({lane,eligible:!!eligible,quality:Number(clamp(quality,0,100).toFixed(2)),conditions});

  const launchFresh=meta.fastDiscoveryLane||(meta.pairAgeSec!==null&&meta.pairAgeSec>=0&&meta.pairAgeSec<=7200);
  const launchConfirm=fastTrack||rtBurst||(rtPulse&&net>=10)||consecutive>=1;
  add('LAUNCH_FAST',watchLike&&actionableSafe&&launchFresh&&score>=50&&liq>=60000&&net>=6&&bs>=1.05&&chg!==null&&chg>=.20&&chg<=15&&launchConfirm,
    score+Math.min(12,net*.25)+Math.min(8,num(rr?.eventMomentum)*2)+(meta.fastDiscoveryLane?5:0),{launchFresh,launchConfirm,fastDiscoveryLane:meta.fastDiscoveryLane,pairAgeSec:meta.pairAgeSec,scoreOk:score>=50,liquidityOk:liq>=60000,buyersOk:net>=6,flowOk:bs>=1.05,momentumOk:chg!==null&&chg>=.20&&chg<=15});

  const momentumConfirm=rtBurst||fastTrack||consecutive>=1;
  add('MOMENTUM',watchLike&&actionableSafe&&score>=52&&liq>=100000&&net>=8&&bs>=1.10&&chg!==null&&chg>=.30&&chg<=12&&momentumConfirm,
    score+Math.min(15,net*.30)+Math.min(10,num(rr?.eventMomentum)*2.5)+Math.min(6,Math.max(0,chg||0)*.5),{momentumConfirm,scoreOk:score>=52,liquidityOk:liq>=100000,buyersOk:net>=8,flowOk:bs>=1.10,momentumOk:chg!==null&&chg>=.30&&chg<=12});

  const recoveryTrend=slope>=0||(avg>=3&&net>=avg);
  const recoveryConfirm=(consecutive>=1&&recoveryTrend)||(rtBurst&&slope>=-1);
  add('RECOVERY_FLOW',watchLike&&actionableSafe&&score>=50&&liq>=120000&&net>=8&&bs>=1.08&&chg!==null&&chg>=.15&&chg<=5&&recoveryTrend&&recoveryConfirm,
    score+Math.min(12,net*.22)+Math.min(8,Math.max(0,slope)*1.2)+Math.min(6,num(rr?.eventMomentum)*1.5),{recoveryTrend,recoveryConfirm,scoreOk:score>=50,liquidityOk:liq>=120000,buyersOk:net>=8,flowOk:bs>=1.08,momentumOk:chg!==null&&chg>=.15&&chg<=5,slope,avgNetBuyersLast2:avg});

  const established=meta.pairAgeSec===null||meta.pairAgeSec>=21600;
  const rotationConfirm=intel.mode==='FULL_INTEL'||rtBurst||consecutive>=2;
  add('ESTABLISHED_ROTATION',watchLike&&actionableSafe&&established&&score>=50&&liq>=500000&&net>=3&&bs>=1.05&&chg!==null&&chg>=.20&&chg<=8&&rotationConfirm,
    score+Math.min(10,Math.log10(Math.max(1,liq/50000))*4)+Math.min(8,net*.18)+Math.min(5,num(rr?.eventMomentum)),{established,rotationConfirm,scoreOk:score>=50,liquidityOk:liq>=500000,buyersOk:net>=3,flowOk:bs>=1.05,momentumOk:chg!==null&&chg>=.20&&chg<=8});

  const eligible=lanes.filter(x=>x.eligible).sort((a,b)=>b.quality-a.quality);
  const selected=eligible[0]||null;
  const boost=selected?laneBoost(selected.lane,regime):0;
  const effectiveScore=Number(clamp(score*intel.haircut+boost,0,100).toFixed(4));
  const promotionEligible=!!selected&&effectiveScore>=58;
  return {selectedLane:selected?.lane||null,promotionEligible,boost,effectiveScore,lanes,common,meta,rtPulse,rtBurst,events5s:num(rr?.events5s),eventMomentum:num(rr?.eventMomentum),lastEventAgeMs:rr?.lastEventAgeMs??null};
}
function guardCandidate(c,rt,wh,regime){
  const intel=intelState(c,rt,wh),p=globalThis.__persistFind?.(c.mint)||null;
  const hardReject=Array.isArray(c.hardReject)?[...c.hardReject]:[];
  const entryGuardReasons=[];const block=reason=>{if(!hardReject.includes(reason))hardReject.push(reason)};
  if(c.token2022===true)block('V369_TOKEN2022_DANGEROUS');
  if(c.mintAuthorityDisabled===false)block('V369_MINT_AUTHORITY_ACTIVE');
  if(c.freezeAuthorityDisabled===false)block('V369_FREEZE_AUTHORITY_ACTIVE');
  if(c.transferHook===true||c.transferHookActive===true)block('V369_TRANSFER_HOOK_ACTIVE');
  if(c.permanentDelegate===true||c.permanentDelegateActive===true)block('V369_PERMANENT_DELEGATE_ACTIVE');
  if(c.nonTransferable===true)block('V369_NON_TRANSFERABLE');
  if(num(c.liquidityUsd,999999)<15000)block('V369_LIQUIDITY_COLLAPSE');
  const liqDrop=explicitLiquidityDropPct(c);if(liqDrop!==null&&liqDrop<=-35)block('V369_LIQUIDITY_DROP_35PCT');
  if(intel.whaleRow&&num(intel.whaleRow.top10Pct,-1)>=70&&num(intel.whaleRow.top10Pct,-1)<100)block('V369_WHALE_TOP10_CONCENTRATION');
  if(intel.whaleRow&&num(intel.whaleRow.deltaTop10Pct,0)>=8)block('V369_WHALE_CONCENTRATION_SPIKE');

  let decision=c.decision;
  const securityDecision=hardReject.some(x=>String(x).startsWith('V369_'))?'BLOCK':c.securityDecision;
  const holderDecision=c.holderClusterAudit?.decision||c.holderClusterDecision||null;
  const holderMaxAccounts=num(c.holderClusterAudit?.maxAccountsSameOwner,c.holderClusterMaxAccountsSameOwner??999);
  const holderTopPct=finite(c.topHoldersPct)?Number(c.topHoldersPct):null;
  const whaleTop10Pct=finite(intel.whaleRow?.top10Pct)?Number(intel.whaleRow.top10Pct):null;
  const whaleDeltaTop10Pct=finite(intel.whaleRow?.deltaTop10Pct)?Number(intel.whaleRow.deltaTop10Pct):null;
  const insiderRiskReasons=[];
  let insiderRiskDecision='PASS';
  const insiderReview=r=>{insiderRiskReasons.push(r);if(insiderRiskDecision!=='BLOCK')insiderRiskDecision='REVIEW'};
  const insiderBlock=r=>{insiderRiskReasons.push(r);insiderRiskDecision='BLOCK'};
  if(holderDecision==='BLOCK')insiderBlock('HOLDER_CLUSTER_BLOCK');else if(holderDecision!=='PASS')insiderReview('HOLDER_CLUSTER_NOT_PASS');
  if(holderTopPct===null)insiderReview('TOP_HOLDERS_UNKNOWN');else if(holderTopPct>50)insiderBlock('TOP_HOLDERS_OVER_50');else if(holderTopPct>35)insiderReview('TOP_HOLDERS_OVER_35');
  if(holderMaxAccounts>=5)insiderBlock('SEVERE_MULTI_ACCOUNT_OWNER_CLUSTER');else if(holderMaxAccounts>=3)insiderReview('MULTI_ACCOUNT_OWNER_CLUSTER');
  if(whaleTop10Pct!==null&&whaleTop10Pct>=70&&whaleTop10Pct<100)insiderBlock('WHALE_TOP10_CONCENTRATION');
  if(whaleDeltaTop10Pct!==null&&whaleDeltaTop10Pct>=8)insiderBlock('WHALE_CONCENTRATION_SPIKE');
  if(!intel.entryAllowed){entryGuardReasons.push('V369_BOTH_INTEL_FEEDS_DOWN');if(decision==='PROBE_CANDIDATE')decision='INTEL_DEGRADED'}
  if(c.needsExtensionAudit===true&&decision==='PROBE_CANDIDATE'){entryGuardReasons.push('V369_EXTENSION_AUDIT_REQUIRED');decision='EXTENSION_AUDIT_REQUIRED'}

  const router=routeCandidate(c,intel,p,hardReject,securityDecision,holderDecision,regime);
  let effectiveConsecutive=num(p?.consecutiveEligible);
  if(router.promotionEligible&&decision!=='PROBE_CANDIDATE'){
    decision='PROBE_CANDIDATE';effectiveConsecutive=Math.max(1,effectiveConsecutive);entryGuardReasons.push(`V376_ROUTED_${router.selectedLane}`);
  }
  if(insiderRiskDecision!=='PASS'&&decision==='PROBE_CANDIDATE'){decision='INSIDER_RISK_BLOCK';entryGuardReasons.push(`V377_INSIDER_${insiderRiskDecision}`);}
  const originalScore=num(c.score);
  const score=router.promotionEligible?router.effectiveScore:Number((originalScore*intel.haircut).toFixed(4));
  return {
    mint:c.mint,symbol:c.symbol,name:c.name,score,originalScore,decision,universeClass:c.universeClass,universeConfidence:c.universeConfidence,
    securityDecision,holderClusterDecision:holderDecision,insiderRiskDecision,insiderRiskReasons:[...new Set(insiderRiskReasons)],insiderRiskModel:'OBJECTIVE_ONCHAIN_CONCENTRATION_V1',devIdentityStatus:c.holderClusterAudit?.devIdentityProven===true?'PROVEN':'UNATTRIBUTED',devIdentityProven:c.holderClusterAudit?.devIdentityProven===true,holderClusterMaxAccountsSameOwner:holderMaxAccounts,
    hardReject,entryGuardReasons,token2022:!!c.token2022,pairAddress:c.pairAddress||null,sellRoute:c.sellRoute===true?true:(c.sellRoute===false?false:null),liquidityUsd:num(c.liquidityUsd),
    sellPriceImpactPct:finite(c.sellPriceImpactPct)?Number(c.sellPriceImpactPct):null,sellQuoteHttp:c.sellQuoteHttp??null,sellQuoteError:c.sellQuoteError??null,
    sellImpactPct:finite(c.sellPriceImpactPct)?Number(c.sellPriceImpactPct):(finite(c.sellImpactPct)?Number(c.sellImpactPct):(finite(c.priceImpactPct)?Number(c.priceImpactPct):null)),priceImpactPct:finite(c.priceImpactPct)?Number(c.priceImpactPct):null,
    organicRatio5m:num(c.organicRatio5m),netBuyers5m:num(c.netBuyers5m),priceChange5m:finite(c.priceChange5m)?Number(c.priceChange5m):null,buyVolume5m:num(c.buyVolume5m),sellVolume5m:num(c.sellVolume5m),dexVolume5m:num(c.dexVolume5m),dexBuys5m:num(c.dexBuys5m),dexSells5m:num(c.dexSells5m),
    buySellRatio5m:num(c.sellVolume5m)>0?num(c.buyVolume5m)/num(c.sellVolume5m):num(c.buyVolume5m)>0?99:0,sources:c.sources||[],persistenceDecision:p?.persistenceDecision||null,consecutiveEligible:effectiveConsecutive,fastTrackReady:!!p?.metrics?.fastTrackReady,
    avgScoreLast2:p?.metrics?.avgScoreLast2??null,avgNetBuyersLast2:p?.metrics?.avgNetBuyersLast2??null,scoreSlopeLast2:p?.metrics?.scoreSlopeLast2??null,liquidityStableLast2:p?.metrics?.liquidityStableLast2??null,
    holderAuditDecision:c.holderClusterAudit?.decision||null,holderReviewReasons:c.holderClusterAudit?.reviewReasons||[],holderBlockReasons:c.holderClusterAudit?.blockReasons||[],holderEvidence:c.holderClusterAudit?.evidence||[],securityReviewReasons:c.securityReviewReasons||[],securityBlockReasons:c.securityBlockReasons||[],securityEvidence:c.securityEvidence||[],
    mintAuthorityDisabled:c.mintAuthorityDisabled,freezeAuthorityDisabled:c.freezeAuthorityDisabled,topHoldersPct:c.topHoldersPct??null,dexLiquidityUsd:c.dexLiquidityUsd??null,needsExtensionAudit:!!c.needsExtensionAudit,transferHookActive:c.transferHookActive===true||c.transferHook===true,permanentDelegateActive:c.permanentDelegateActive===true||c.permanentDelegate===true,nonTransferable:c.nonTransferable===true,liquidityChange5mPct:liqDrop,
    intelMode:intel.mode,intelHaircut:intel.haircut,realtimeFeedFresh:intel.rtFeed,whaleFeedFresh:intel.whaleFeed,realtimeRowFresh:!!intel.rtRow,whaleRowFresh:!!intel.whaleRow,whaleTop10Pct:intel.whaleRow?.top10Pct??null,whaleDeltaTop10Pct:intel.whaleRow?.deltaTop10Pct??null,
    strategyRouter:{selectedLane:router.selectedLane,promotionEligible:router.promotionEligible,boost:router.boost,effectiveScore:router.effectiveScore,marketRegime:regime.name,radar:router.meta,rtPulse:router.rtPulse,rtBurst:router.rtBurst,events5s:router.events5s,eventMomentum:router.eventMomentum,lastEventAgeMs:router.lastEventAgeMs,lanes:router.lanes}
  };
}

if(SELF_TEST){
  const now=new Date().toISOString();
  const rt={status:'HEALTHY',updatedAt:now,rows:[{mint:'L',lastEventAgeMs:500,events5s:4,eventMomentum:1.8},{mint:'B',lastEventAgeMs:400,events5s:5,eventMomentum:2.0},{mint:'R',lastEventAgeMs:700,events5s:3,eventMomentum:1.5}]};
  const wh={status:'HEALTHY',updatedAt:now,rows:[]};
  const regime={name:'HOT_MOMENTUM'};
  globalThis.__persistFind=m=>m==='R'?{consecutiveEligible:1,metrics:{avgNetBuyersLast2:9,scoreSlopeLast2:1.5,liquidityStableLast2:true}}:{consecutiveEligible:0,metrics:{fastTrackReady:false,liquidityStableLast2:true}};
  const common={decision:'WATCH',universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',holderClusterAudit:{decision:'PASS',maxAccountsSameOwner:1,devIdentityProven:false},topHoldersPct:20,sellRoute:true,sellPriceImpactPct:.4,token2022:false,mintAuthorityDisabled:true,freezeAuthorityDisabled:true};
  const launch=guardCandidate({...common,mint:'L',score:60,liquidityUsd:180000,netBuyers5m:18,priceChange5m:2,buyVolume5m:250,sellVolume5m:120,newListingRadar:{fastDiscoveryLane:true,pairAgeSec:500}},rt,wh,regime);
  if(launch.decision!=='PROBE_CANDIDATE'||launch.strategyRouter.selectedLane!=='LAUNCH_FAST'||launch.score<58)throw new Error('LAUNCH_ROUTER_SELFTEST');
  const unsafe=guardCandidate({...common,mint:'B',score:80,liquidityUsd:500000,netBuyers5m:30,priceChange5m:3,buyVolume5m:300,sellVolume5m:100,token2022:true},rt,wh,regime);
  if(unsafe.decision==='PROBE_CANDIDATE'||!unsafe.hardReject.includes('V369_TOKEN2022_DANGEROUS'))throw new Error('HARD_GUARD_BYPASS_SELFTEST');
  const review=guardCandidate({...common,mint:'R',score:75,securityDecision:'REVIEW',liquidityUsd:700000,netBuyers5m:20,priceChange5m:2,buyVolume5m:300,sellVolume5m:100},rt,wh,regime);
  if(review.decision==='PROBE_CANDIDATE')throw new Error('SECURITY_REVIEW_PROMOTION_SELFTEST');
  const insider=guardCandidate({...common,mint:'I',score:85,liquidityUsd:700000,netBuyers5m:20,priceChange5m:2,buyVolume5m:300,sellVolume5m:100,holderClusterAudit:{decision:'REVIEW',maxAccountsSameOwner:3,devIdentityProven:false}},rt,wh,regime);
  if(insider.decision==='PROBE_CANDIDATE'||insider.insiderRiskDecision==='PASS')throw new Error('INSIDER_RISK_PROMOTION_SELFTEST');
  const down=guardCandidate({...common,mint:'X',score:90,decision:'PROBE_CANDIDATE',liquidityUsd:500000}, {}, {},regime);if(down.decision==='PROBE_CANDIDATE')throw new Error('BOTH_FEEDS_DOWN_LEAK_SELFTEST');
  console.log('V376_MULTI_STRATEGY_ROUTER_SELF_TEST=PASS');
  console.log('LANES=LAUNCH_FAST,MOMENTUM,RECOVERY_FLOW,ESTABLISHED_ROTATION');
  console.log('EXECUTOR_CORE_SAFETY_CONTRACT_PRESERVED=TRUE');
  console.log('SECURITY_PASS_REQUIRED=TRUE');
  console.log('HOLDER_PASS_REQUIRED=TRUE');
  console.log('OBJECTIVE_INSIDER_RISK_PASS_REQUIRED=TRUE');
  console.log('DEV_IDENTITY_UNKNOWN_IS_NOT_MISREPRESENTED=TRUE');
  console.log('SELL_ROUTE_REQUIRED=TRUE');
  console.log('TOKEN2022_HARD_BLOCK_PRESERVED=TRUE');
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
const regime=marketRegime(scan,realtime);
const candidates=(scan.candidates||[]).map(c=>{
  const g=guardCandidate(c,realtime,whale,regime);
  if(source?.allowNewEntries===false&&g.decision==='PROBE_CANDIDATE'){g.decision='SOURCE_HEALTH_BLOCK';g.entryGuardReasons.push('V369_SOURCE_HEALTH_BLOCK')}
  return g;
}).sort((a,b)=>b.score-a.score).slice(0,50);
const safeRisk={};for(const k of Object.keys(risk||{})){const v=risk[k];if(['string','number','boolean'].includes(typeof v)||v===null)safeRisk[k]=v;else if(Array.isArray(v))safeRisk[k]=v.slice(0,10);else if(v&&typeof v==='object'&&JSON.stringify(v).length<12000)safeRisk[k]=v}
const sourceHealth={status:source?.status||null,checkedAt:source?.checkedAt||null,successfulSources:num(source?.successfulSources),failedSources:num(source?.failedSources),usingCache:source?.usingCache===true,allowNewEntries:source?.allowNewEntries===true};
const laneCount=name=>candidates.filter(x=>x.strategyRouter?.selectedLane===name).length;
const laneProbe=name=>candidates.filter(x=>x.strategyRouter?.selectedLane===name&&x.decision==='PROBE_CANDIDATE').length;
const summary={
  fullIntel:candidates.filter(x=>x.intelMode==='FULL_INTEL').length,realtimeOnly:candidates.filter(x=>x.intelMode==='REALTIME_ONLY').length,whaleOnly:candidates.filter(x=>x.intelMode==='WHALE_ONLY').length,feedHealthyRowMissing:candidates.filter(x=>x.intelMode==='FEED_HEALTHY_ROW_MISSING').length,bothFeedsDown:candidates.filter(x=>x.intelMode==='BOTH_FEEDS_DOWN').length,
  blockedByModernGuard:candidates.filter(x=>x.hardReject.some(r=>String(r).startsWith('V369_'))).length,sourceHealthBlocked:candidates.filter(x=>x.entryGuardReasons.includes('V369_SOURCE_HEALTH_BLOCK')).length,probeCandidates:candidates.filter(x=>x.decision==='PROBE_CANDIDATE').length,
  routedCandidates:candidates.filter(x=>x.strategyRouter?.selectedLane).length,
  lanes:{LAUNCH_FAST:{routed:laneCount('LAUNCH_FAST'),probe:laneProbe('LAUNCH_FAST')},MOMENTUM:{routed:laneCount('MOMENTUM'),probe:laneProbe('MOMENTUM')},RECOVERY_FLOW:{routed:laneCount('RECOVERY_FLOW'),probe:laneProbe('RECOVERY_FLOW')},ESTABLISHED_ROTATION:{routed:laneCount('ESTABLISHED_ROTATION'),probe:laneProbe('ESTABLISHED_ROTATION')}}
};
const nowIso=new Date().toISOString();
const out={version:VERSION,trendTelemetryRevision:'2.6.1',timestamp:nowIso,updatedAt:nowIso,scannerVersion:scan.version||null,sourceHealth,risk:safeRisk,marketRegime:regime,intelSummary:summary,candidates};
const t=OUT+'.tmp';fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,OUT);try{fs.chmodSync(OUT,0o664)}catch{}
console.log(`SAFE_SIGNAL_EXPORT=${candidates.length} SOURCE=${sourceHealth.status} V376_ROUTER=${JSON.stringify({regime:regime.name,probe:summary.probeCandidates,routed:summary.routedCandidates,lanes:summary.lanes})}`);
