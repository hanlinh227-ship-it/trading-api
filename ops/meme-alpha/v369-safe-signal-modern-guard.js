import fs from 'node:fs';

const P='/var/lib/meme-alpha/data/paper';
const OUT='/opt/meme-alpha/app/runtime-status/signal-snapshot.json';
const REALTIME='/opt/meme-alpha/app/runtime-status/realtime-pool-pulse.json';
const WHALE='/opt/meme-alpha/app/runtime-status/whale-flow-intel.json';
const SELF_TEST=process.argv.includes('--self-test');

const readFile=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const read=(n,d={})=>readFile(`${P}/${n}`,d);
const num=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const ageSec=(ts)=>{const t=Date.parse(ts||0);return Number.isFinite(t)?Math.max(0,(Date.now()-t)/1000):Infinity};
const badStatus=(s)=>new Set(['DEGRADED','INTERNAL_ERROR','ERROR','OFFLINE','STALE','RATE_LIMIT_BACKOFF','WARMING_UP']).has(String(s||'').toUpperCase());
const feedHealthy=(x,maxAge)=>!!x&&!badStatus(x.status)&&ageSec(x.updatedAt||x.timestamp||x.generatedAt)<=maxAge;
const rowAgeSec=(r,parent)=>ageSec(r?.observedAt||r?.updatedAt||r?.timestamp||parent?.updatedAt||parent?.timestamp||parent?.generatedAt);

function freshRow(doc,mint,maxAge,kind){
  const r=(doc?.rows||[]).find(x=>x?.mint===mint);
  if(!r)return null;
  if(kind==='realtime'&&Number.isFinite(Number(r.lastEventAgeMs)))return Number(r.lastEventAgeMs)<=maxAge*1000?r:null;
  return rowAgeSec(r,doc)<=maxAge?r:null;
}

function intelState(c,rt,wh){
  if(SELF_TEST)return {mode:'SELF_TEST',haircut:1,entryAllowed:true,rtFeed:true,whaleFeed:true,rtRow:true,whaleRow:true,whale:null};
  const rtFeed=feedHealthy(rt,15), whaleFeed=feedHealthy(wh,180);
  const rr=rtFeed?freshRow(rt,c.mint,8,'realtime'):null;
  const wr=whaleFeed?freshRow(wh,c.mint,120,'whale'):null;
  let mode='BOTH_FEEDS_DOWN',haircut=0;
  if(rr&&wr){mode='FULL_INTEL';haircut=1}
  else if(rr){mode='REALTIME_ONLY';haircut=.88}
  else if(wr){mode='WHALE_ONLY';haircut=.76}
  else if(rtFeed||whaleFeed){mode='FEED_HEALTHY_ROW_MISSING';haircut=.66}
  return {mode,haircut,entryAllowed:rtFeed||whaleFeed,rtFeed,whaleFeed,rtRow:!!rr,whaleRow:!!wr,whale:wr};
}

function explicitLiquidityDropPct(c){
  for(const k of ['liquidityChange5mPct','liquidityDelta5mPct','liquidityChangePct5m','liquidityDrop5mPct']){
    if(Number.isFinite(Number(c?.[k])))return Number(c[k]);
  }
  return null;
}

function guardCandidate(c,rt,wh){
  const intel=intelState(c,rt,wh);
  const p=globalThis.__persistFind?.(c.mint)||null;
  const hardReject=Array.isArray(c.hardReject)?[...c.hardReject]:[];
  const entryGuardReasons=[];
  const block=(reason)=>{if(!hardReject.includes(reason))hardReject.push(reason)};

  if(c.token2022===true)block('V369_TOKEN2022_DANGEROUS');
  if(c.mintAuthorityDisabled===false)block('V369_MINT_AUTHORITY_ACTIVE');
  if(c.freezeAuthorityDisabled===false)block('V369_FREEZE_AUTHORITY_ACTIVE');
  if(c.transferHook===true||c.transferHookActive===true)block('V369_TRANSFER_HOOK_ACTIVE');
  if(c.permanentDelegate===true||c.permanentDelegateActive===true)block('V369_PERMANENT_DELEGATE_ACTIVE');
  if(c.nonTransferable===true)block('V369_NON_TRANSFERABLE');
  if(num(c.liquidityUsd,999999)<15000)block('V369_LIQUIDITY_COLLAPSE');
  const liqDrop=explicitLiquidityDropPct(c);
  if(liqDrop!==null&&liqDrop<=-35)block('V369_LIQUIDITY_DROP_35PCT');
  if(intel.whale&&num(intel.whale.top10Pct,-1)>=70&&num(intel.whale.top10Pct,-1)<100)block('V369_WHALE_TOP10_CONCENTRATION');
  if(intel.whale&&num(intel.whale.deltaTop10Pct,0)>=8)block('V369_WHALE_CONCENTRATION_SPIKE');

  let decision=c.decision;
  if(!intel.entryAllowed){entryGuardReasons.push('V369_BOTH_INTEL_FEEDS_DOWN');if(decision==='PROBE_CANDIDATE')decision='INTEL_DEGRADED'}
  if(c.needsExtensionAudit===true&&decision==='PROBE_CANDIDATE'){entryGuardReasons.push('V369_EXTENSION_AUDIT_REQUIRED');decision='EXTENSION_AUDIT_REQUIRED'}
  const securityDecision=hardReject.some(x=>String(x).startsWith('V369_'))?'BLOCK':c.securityDecision;
  const originalScore=num(c.score);
  const score=intel.entryAllowed?Number((originalScore*intel.haircut).toFixed(4)):0;

  return {
    mint:c.mint,symbol:c.symbol,name:c.name,score,originalScore,decision,
    universeClass:c.universeClass,universeConfidence:c.universeConfidence,
    securityDecision,
    holderClusterDecision:c.holderClusterAudit?.decision||c.holderClusterDecision||null,
    devIdentityProven:c.holderClusterAudit?.devIdentityProven===true,
    holderClusterMaxAccountsSameOwner:num(c.holderClusterAudit?.maxAccountsSameOwner),
    hardReject,entryGuardReasons,
    token2022:!!c.token2022,
    sellRoute:c.sellRoute===true?true:(c.sellRoute===false?false:null),
    liquidityUsd:num(c.liquidityUsd),
    sellPriceImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):null,
    sellQuoteHttp:c.sellQuoteHttp??null,sellQuoteError:c.sellQuoteError??null,
    sellImpactPct:Number.isFinite(Number(c.sellPriceImpactPct))?Number(c.sellPriceImpactPct):(Number.isFinite(Number(c.sellImpactPct))?Number(c.sellImpactPct):(Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null)),
    priceImpactPct:Number.isFinite(Number(c.priceImpactPct))?Number(c.priceImpactPct):null,
    organicRatio5m:num(c.organicRatio5m),netBuyers5m:num(c.netBuyers5m),
    priceChange5m:Number.isFinite(Number(c.priceChange5m))?Number(c.priceChange5m):null,
    buyVolume5m:num(c.buyVolume5m),sellVolume5m:num(c.sellVolume5m),dexVolume5m:num(c.dexVolume5m),dexBuys5m:num(c.dexBuys5m),dexSells5m:num(c.dexSells5m),
    buySellRatio5m:num(c.sellVolume5m)>0?num(c.buyVolume5m)/num(c.sellVolume5m):num(c.buyVolume5m)>0?99:0,
    sources:c.sources||[],
    persistenceDecision:p?.persistenceDecision||null,consecutiveEligible:num(p?.consecutiveEligible),
    fastTrackReady:!!p?.metrics?.fastTrackReady,avgScoreLast2:p?.metrics?.avgScoreLast2??null,avgNetBuyersLast2:p?.metrics?.avgNetBuyersLast2??null,scoreSlopeLast2:p?.metrics?.scoreSlopeLast2??null,liquidityStableLast2:p?.metrics?.liquidityStableLast2??null,
    holderAuditDecision:c.holderClusterAudit?.decision||null,holderReviewReasons:c.holderClusterAudit?.reviewReasons||[],holderBlockReasons:c.holderClusterAudit?.blockReasons||[],holderEvidence:c.holderClusterAudit?.evidence||[],
    securityReviewReasons:c.securityReviewReasons||[],securityBlockReasons:c.securityBlockReasons||[],securityEvidence:c.securityEvidence||[],
    mintAuthorityDisabled:c.mintAuthorityDisabled,freezeAuthorityDisabled:c.freezeAuthorityDisabled,topHoldersPct:c.topHoldersPct??null,dexLiquidityUsd:c.dexLiquidityUsd??null,needsExtensionAudit:!!c.needsExtensionAudit,
    transferHookActive:c.transferHookActive===true||c.transferHook===true,permanentDelegateActive:c.permanentDelegateActive===true||c.permanentDelegate===true,nonTransferable:c.nonTransferable===true,
    liquidityChange5mPct:liqDrop,
    intelMode:intel.mode,intelHaircut:intel.haircut,realtimeFeedFresh:intel.rtFeed,whaleFeedFresh:intel.whaleFeed,realtimeRowFresh:intel.rtRow,whaleRowFresh:intel.whaleRow,
    whaleTop10Pct:intel.whale?.top10Pct??null,whaleDeltaTop10Pct:intel.whale?.deltaTop10Pct??null
  };
}

if(SELF_TEST){
  const now=new Date().toISOString();
  const rt={status:'HEALTHY',updatedAt:now,rows:[{mint:'A',lastEventAgeMs:1000}]};
  const wh={status:'HEALTHY',updatedAt:now,rows:[{mint:'A',observedAt:now,top10Pct:75,deltaTop10Pct:9}]};
  globalThis.__persistFind=()=>({consecutiveEligible:3,metrics:{avgNetBuyersLast2:5}});
  const a=guardCandidate({mint:'A',score:80,decision:'PROBE_CANDIDATE',securityDecision:'ALLOW',sellRoute:true,liquidityUsd:200000},rt,wh);
  if(a.securityDecision!=='BLOCK'||!a.hardReject.includes('V369_WHALE_TOP10_CONCENTRATION'))throw new Error('WHALE_RUG_GUARD_SELFTEST');
  const b=intelState({mint:'B'}, {}, {});if(b.entryAllowed!==false||b.haircut!==0)throw new Error('INTEL_FAIL_CLOSED_SELFTEST');
  const c=guardCandidate({mint:'A',score:80,decision:'PROBE_CANDIDATE',securityDecision:'ALLOW',sellRoute:true,liquidityUsd:200000,needsExtensionAudit:true},rt,{status:'RATE_LIMIT_BACKOFF',updatedAt:now,rows:[]});
  if(c.decision!=='EXTENSION_AUDIT_REQUIRED'||c.intelHaircut!==0.88)throw new Error('EXTENSION_OR_HAIRCUT_SELFTEST');
  console.log('V369_SIGNAL_GUARD_SELF_TEST=PASS');
  console.log('ENTRY_FAIL_CLOSED_WHEN_BOTH_INTEL_DOWN=TRUE');
  console.log('DEGRADED_INTEL_SCORE_HAIRCUT=TRUE');
  console.log('FRESH_WHALE_RUG_GUARD=TRUE');
  console.log('TOKEN_EXTENSION_ENTRY_GUARD=TRUE');
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

const candidates=(scan.candidates||[]).map(c=>guardCandidate(c,realtime,whale)).sort((a,b)=>b.score-a.score).slice(0,30);
const safeRisk={};for(const k of Object.keys(risk||{})){const v=risk[k];if(['string','number','boolean'].includes(typeof v)||v===null)safeRisk[k]=v;else if(Array.isArray(v))safeRisk[k]=v.slice(0,10);else if(v&&typeof v==='object'&&JSON.stringify(v).length<12000)safeRisk[k]=v}
const sourceHealth={status:source?.status||null,checkedAt:source?.checkedAt||null,successfulSources:num(source?.successfulSources),failedSources:num(source?.failedSources),usingCache:source?.usingCache===true,allowNewEntries:source?.allowNewEntries===true};
const summary={fullIntel:candidates.filter(x=>x.intelMode==='FULL_INTEL').length,realtimeOnly:candidates.filter(x=>x.intelMode==='REALTIME_ONLY').length,whaleOnly:candidates.filter(x=>x.intelMode==='WHALE_ONLY').length,feedHealthyRowMissing:candidates.filter(x=>x.intelMode==='FEED_HEALTHY_ROW_MISSING').length,bothFeedsDown:candidates.filter(x=>x.intelMode==='BOTH_FEEDS_DOWN').length,blockedByModernGuard:candidates.filter(x=>x.hardReject.some(r=>String(r).startsWith('V369_'))).length};
const out={version:'3.69.0-modern-signal-guard',trendTelemetryRevision:'2.6.0',timestamp:new Date().toISOString(),scannerVersion:scan.version||null,sourceHealth,risk:safeRisk,intelSummary:summary,candidates};
const t=OUT+'.tmp';fs.writeFileSync(t,JSON.stringify(out,null,2));fs.renameSync(t,OUT);try{fs.chmodSync(OUT,0o664)}catch{}
console.log(`SAFE_SIGNAL_EXPORT=${candidates.length} SOURCE=${sourceHealth.status} V369_INTEL=${JSON.stringify(summary)}`);
