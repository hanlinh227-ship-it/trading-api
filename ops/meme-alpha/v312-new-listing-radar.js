import fs from 'node:fs';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const OUT=`${APP}/runtime-status/new-listing-radar.json`;
const STATE=`${DATA}/new-listing-radar.json`;
const LOCK='/tmp/meme-alpha-new-listing-radar.lock';
const DEX='https://api.dexscreener.com';
const runtime=read(`${APP}/config/runtime.json`,{});
const JUP=String(runtime.jupiter||'https://api.jup.ag').replace(/\/$/,'');
const MAX_MINTS=60;
const MAX_AGE_KEEP_MS=6*60*60*1000;

function atomic(path,value){
  const t=`${path}.tmp-${process.pid}`;
  fs.writeFileSync(t,JSON.stringify(value,null,2));
  fs.renameSync(t,path);
  try{fs.chmodSync(path,0o664)}catch{}
}
function writeRuntime(value){
  const text=JSON.stringify(value,null,2);
  try{
    atomic(OUT,value);
    return;
  }catch(e){
    // runtime-status may intentionally deny directory creation to the service user.
    // Deployment pre-creates this non-sensitive state file, so direct overwrite is safe.
    fs.writeFileSync(OUT,text);
    try{fs.chmodSync(OUT,0o666)}catch{}
    console.log(`RADAR_RUNTIME_DIRECT_WRITE=${String(e?.code||e?.message||e).slice(0,80)}`);
  }
}
function read(path,d={}){try{return JSON.parse(fs.readFileSync(path,'utf8'))}catch{return d}}
function arr(x){return Array.isArray(x)?x:(x&&typeof x==='object'?[x]:[])}
function n(v,d=0){const x=Number(v);return Number.isFinite(x)?x:d}
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
async function get(url,timeout=3500){
  const r=await fetch(url,{headers:{accept:'application/json'},signal:AbortSignal.timeout(timeout)});
  if(!r.ok) throw new Error(`HTTP_${r.status}`);
  return await r.json();
}
function ensure(map,mint){
  if(!map.has(mint)) map.set(mint,{mint,sources:new Set(),profile:{},jupiter:{}});
  return map.get(mint);
}

let lockFd=null;
try{
  try{lockFd=fs.openSync(LOCK,'wx')}catch{
    try{const st=fs.statSync(LOCK);if(Date.now()-st.mtimeMs>15000){fs.unlinkSync(LOCK);lockFd=fs.openSync(LOCK,'wx')}}catch{}
  }
  if(lockFd===null){console.log('RADAR_SKIP_LOCKED');process.exit(0)}
  fs.writeFileSync(lockFd,String(process.pid));

  const sourceMap=new Map();
  const failures=[];
  let healthySources=0;
  let jupiterRecentOk=false;
  let jupiterRecentCount=0;
  let dexSolanaPromoMints=0;

  try{
    const body=await get(`${JUP}/tokens/v2/recent`,5000);
    const rows=arr(body);
    jupiterRecentOk=true;
    healthySources++;
    jupiterRecentCount=rows.length;
    for(const row of rows){
      const mint=String(row?.id||row?.address||row?.mint||'').trim();
      if(!mint) continue;
      const x=ensure(sourceMap,mint);
      x.sources.add('jupiter-recent');
      x.jupiter={
        symbol:row?.symbol||null,
        name:row?.name||null,
        decimals:Number.isFinite(Number(row?.decimals))?Number(row.decimals):null,
        holderCount:n(row?.holderCount),
        liquidityUsd:n(row?.liquidity),
        organicScore:n(row?.organicScore),
        firstPoolId:row?.firstPool?.id||null,
        firstPoolCreatedAt:row?.firstPool?.createdAt||null,
        stats5m:row?.stats5m||null,
        audit:row?.audit||null
      };
      if(row?.icon) x.profile.icon=row.icon;
    }
  }catch(e){
    failures.push({source:'jupiter-recent',error:String(e?.message||e).slice(0,120)});
  }

  const feeds=[
    ['profile',`${DEX}/token-profiles/latest/v1`],
    ['boost',`${DEX}/token-boosts/latest/v1`],
    ['community',`${DEX}/community-takeovers/latest/v1`]
  ];
  const settled=await Promise.allSettled(feeds.map(async([source,url])=>[source,await get(url)]));
  const promoSolana=new Set();
  for(let i=0;i<settled.length;i++){
    const source=feeds[i][0],r=settled[i];
    if(r.status!=='fulfilled'){
      failures.push({source,error:String(r.reason?.message||r.reason).slice(0,120)});
      continue;
    }
    healthySources++;
    const body=r.value[1];
    for(const row of arr(body)){
      if(String(row?.chainId||'').toLowerCase()!=='solana') continue;
      const mint=String(row?.tokenAddress||'').trim(); if(!mint) continue;
      promoSolana.add(mint);
      const x=ensure(sourceMap,mint);
      x.sources.add(`dex-${source}`);
      for(const k of ['url','description','icon','header','amount','totalAmount','claimDate']) if(row?.[k]!=null) x.profile[k]=row[k];
      if(Array.isArray(row?.links)) x.profile.links=row.links.slice(0,8);
    }
  }
  dexSolanaPromoMints=promoSolana.size;

  const previous=read(OUT,read(STATE,{candidates:[]}));
  const prevByMint=new Map((previous.candidates||[]).map(x=>[x.mint,x]));
  const rankedMints=[...sourceMap.values()]
    .sort((a,b)=>{
      const ap=a.sources.has('jupiter-recent')?1:0;
      const bp=b.sources.has('jupiter-recent')?1:0;
      if(bp!==ap) return bp-ap;
      return b.sources.size-a.sources.size;
    })
    .slice(0,MAX_MINTS)
    .map(x=>x.mint);

  const pairRows=[];
  let pairLookupOk=false;
  let pairBatchSuccess=0;
  for(let i=0;i<rankedMints.length;i+=30){
    const chunk=rankedMints.slice(i,i+30); if(!chunk.length) continue;
    try{
      const rows=await get(`${DEX}/tokens/v1/solana/${chunk.join(',')}`,5000);
      pairBatchSuccess++;
      pairLookupOk=true;
      if(Array.isArray(rows)) pairRows.push(...rows);
    }catch(e){
      failures.push({source:`dex-pairs-${i/30}`,error:String(e?.message||e).slice(0,120)});
    }
  }
  if(pairBatchSuccess>0) healthySources++;

  const bestByMint=new Map();
  for(const p of pairRows){
    const addresses=[p?.baseToken?.address,p?.quoteToken?.address].filter(Boolean);
    for(const mint of addresses){
      if(!sourceMap.has(mint)) continue;
      const old=bestByMint.get(mint);
      if(!old || n(p?.liquidity?.usd)>n(old?.liquidity?.usd)) bestByMint.set(mint,p);
    }
  }

  const now=Date.now();
  const candidates=[];
  for(const x of sourceMap.values()){
    const p=bestByMint.get(x.mint)||{};
    const j=x.jupiter||{};
    const dexCreatedMs=n(p?.pairCreatedAt,NaN);
    const jupCreatedMs=Date.parse(j.firstPoolCreatedAt||'');
    const createdMs=Number.isFinite(dexCreatedMs)?dexCreatedMs:(Number.isFinite(jupCreatedMs)?jupCreatedMs:NaN);
    const pairAgeSec=Number.isFinite(createdMs)?Math.max(0,(now-createdMs)/1000):null;
    const liq=Math.max(n(p?.liquidity?.usd),n(j.liquidityUsd));
    const jstats=j.stats5m||{};
    const vol5=Math.max(n(p?.volume?.m5),n(jstats?.buyVolume)+n(jstats?.sellVolume),n(jstats?.volume));
    const buys=Math.max(n(p?.txns?.m5?.buys),n(jstats?.numBuys),n(jstats?.buys));
    const sells=Math.max(n(p?.txns?.m5?.sells),n(jstats?.numSells),n(jstats?.sells));
    const ratio=sells>0?buys/sells:(buys>0?4:0);
    let score=0;
    if(x.sources.has('jupiter-recent')) score+=12;
    score+=Math.min(12,(x.sources.size-1)*4);
    if(liq>=250000)score+=25; else if(liq>=100000)score+=20; else if(liq>=50000)score+=15; else if(liq>=25000)score+=10;
    if(pairAgeSec!=null){if(pairAgeSec<=300)score+=20;else if(pairAgeSec<=900)score+=15;else if(pairAgeSec<=3600)score+=10;else if(pairAgeSec<=10800)score+=4}
    if(buys>=50)score+=15;else if(buys>=20)score+=12;else if(buys>=5)score+=7;else if(buys>0)score+=3;
    if(ratio>=2)score+=10;else if(ratio>=1.3)score+=7;else if(ratio>=1)score+=4;
    if(vol5>=100000)score+=8;else if(vol5>=25000)score+=6;else if(vol5>=5000)score+=3;
    if(n(j.organicScore)>=70)score+=5; else if(n(j.organicScore)>=50)score+=3;
    score=clamp(score,0,100);
    const prev=prevByMint.get(x.mint)||{};
    const baseIsMint=p?.baseToken?.address===x.mint;
    candidates.push({
      mint:x.mint,
      symbol:baseIsMint?(p?.baseToken?.symbol||j.symbol||prev.symbol||null):(j.symbol||prev.symbol||null),
      name:baseIsMint?(p?.baseToken?.name||j.name||prev.name||null):(j.name||prev.name||null),
      sources:[...x.sources],
      firstSeenAt:prev.firstSeenAt||new Date().toISOString(),
      lastSeenAt:new Date().toISOString(),
      pairAddress:p?.pairAddress||j.firstPoolId||null,
      dexId:p?.dexId||null,
      pairCreatedAt:Number.isFinite(createdMs)?new Date(createdMs).toISOString():null,
      pairAgeSec:pairAgeSec==null?null:Number(pairAgeSec.toFixed(2)),
      liquidityUsd:liq,
      holderCount:n(j.holderCount),
      organicScore:n(j.organicScore),
      volume5m:vol5,
      buys5m:buys,
      sells5m:sells,
      buySellTxnRatio:Number(ratio.toFixed(3)),
      priceChange5m:Number.isFinite(Number(p?.priceChange?.m5))?Number(p.priceChange.m5):null,
      marketCap:n(p?.marketCap),
      fdv:n(p?.fdv),
      boostsActive:n(p?.boosts?.active),
      preScore:score,
      entryEligible:false,
      purpose:'DISCOVERY_ONLY',
      profile:x.profile
    });
  }

  for(const old of previous.candidates||[]){
    if(sourceMap.has(old.mint)) continue;
    const seen=Date.parse(old.lastSeenAt||old.firstSeenAt||0);
    if(Number.isFinite(seen)&&now-seen<=MAX_AGE_KEEP_MS) candidates.push({...old,entryEligible:false,purpose:'DISCOVERY_ONLY'});
  }
  candidates.sort((a,b)=>b.preScore-a.preScore || n(a.pairAgeSec,1e12)-n(b.pairAgeSec,1e12));

  const discoveryHealthy=(jupiterRecentOk||dexSolanaPromoMints>0)&&sourceMap.size>0;
  const status=(discoveryHealthy&&pairLookupOk)?'HEALTHY':'DEGRADED';
  const out={
    version:'3.18.0',
    updatedAt:new Date().toISOString(),
    status,
    healthySources,
    jupiterRecentOk,
    jupiterRecentCount,
    dexSolanaPromoMints,
    pairLookupOk,
    pairBatchSuccess,
    failures,
    currentFeedMints:sourceMap.size,
    candidates:candidates.slice(0,100),
    policy:'DISCOVERY_ONLY_NEVER_GRANTS_ENTRY'
  };

  writeRuntime(out);
  try{
    atomic(STATE,out);
  }catch(e){
    console.log(`RADAR_PERSISTENCE_WARN=${String(e?.code||e?.message||e).slice(0,120)}`);
  }
  console.log(`NEW_LISTING_RADAR v=${out.version} status=${out.status} jupRecent=${out.jupiterRecentCount} dexPromoSol=${out.dexSolanaPromoMints} feedMints=${out.currentFeedMints} candidates=${out.candidates.length} topScore=${out.candidates[0]?.preScore??0}`);
} finally {
  try{if(lockFd!==null)fs.closeSync(lockFd)}catch{}
  try{fs.unlinkSync(LOCK)}catch{}
}
