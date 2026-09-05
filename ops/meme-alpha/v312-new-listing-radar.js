import fs from 'node:fs';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const OUT=`${APP}/runtime-status/new-listing-radar.json`;
const STATE=`${DATA}/new-listing-radar.json`;
const LOCK='/tmp/meme-alpha-new-listing-radar.lock';
const BASE='https://api.dexscreener.com';
const MAX_MINTS=60;
const MAX_AGE_KEEP_MS=6*60*60*1000;

function atomic(path,value){
  const t=`${path}.tmp-${process.pid}`;
  fs.writeFileSync(t,JSON.stringify(value,null,2));
  fs.renameSync(t,path);
  try{fs.chmodSync(path,0o664)}catch{}
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

let lockFd=null;
try{
  try{lockFd=fs.openSync(LOCK,'wx')}catch{
    try{const st=fs.statSync(LOCK);if(Date.now()-st.mtimeMs>15000){fs.unlinkSync(LOCK);lockFd=fs.openSync(LOCK,'wx')}}catch{}
  }
  if(lockFd===null){console.log('RADAR_SKIP_LOCKED');process.exit(0)}
  fs.writeFileSync(lockFd,String(process.pid));

  const feeds=[
    ['profile',`${BASE}/token-profiles/latest/v1`],
    ['boost',`${BASE}/token-boosts/latest/v1`],
    ['community',`${BASE}/community-takeovers/latest/v1`]
  ];
  const settled=await Promise.allSettled(feeds.map(async([source,url])=>[source,await get(url)]));
  const sourceMap=new Map();
  const failures=[];
  let healthySources=0;
  for(let i=0;i<settled.length;i++){
    const source=feeds[i][0],r=settled[i];
    if(r.status!=='fulfilled'){failures.push({source,error:String(r.reason?.message||r.reason).slice(0,120)});continue}
    healthySources++;
    const body=r.value[1];
    for(const row of arr(body)){
      if(String(row?.chainId||'').toLowerCase()!=='solana') continue;
      const mint=String(row?.tokenAddress||'').trim(); if(!mint) continue;
      if(!sourceMap.has(mint)) sourceMap.set(mint,{mint,sources:new Set(),profile:{}});
      const x=sourceMap.get(mint); x.sources.add(source);
      for(const k of ['url','description','icon','header','amount','totalAmount','claimDate']) if(row?.[k]!=null) x.profile[k]=row[k];
      if(Array.isArray(row?.links)) x.profile.links=row.links.slice(0,8);
    }
  }

  const previous=read(STATE,{candidates:[]});
  const prevByMint=new Map((previous.candidates||[]).map(x=>[x.mint,x]));
  const rankedMints=[...sourceMap.values()]
    .sort((a,b)=>b.sources.size-a.sources.size)
    .slice(0,MAX_MINTS)
    .map(x=>x.mint);

  const pairRows=[];
  for(let i=0;i<rankedMints.length;i+=30){
    const chunk=rankedMints.slice(i,i+30); if(!chunk.length) continue;
    try{
      const rows=await get(`${BASE}/tokens/v1/solana/${chunk.join(',')}`,5000);
      if(Array.isArray(rows)) pairRows.push(...rows);
    }catch(e){failures.push({source:`pairs_${i/30}`,error:String(e?.message||e).slice(0,120)})}
  }

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
    const createdMs=n(p?.pairCreatedAt,NaN);
    const pairAgeSec=Number.isFinite(createdMs)?Math.max(0,(now-createdMs)/1000):null;
    const liq=n(p?.liquidity?.usd);
    const vol5=n(p?.volume?.m5);
    const buys=n(p?.txns?.m5?.buys);
    const sells=n(p?.txns?.m5?.sells);
    const ratio=sells>0?buys/sells:(buys>0?4:0);
    let score=0;
    score+=Math.min(15,x.sources.size*5);
    if(liq>=250000)score+=25; else if(liq>=100000)score+=20; else if(liq>=50000)score+=15; else if(liq>=25000)score+=10;
    if(pairAgeSec!=null){if(pairAgeSec<=300)score+=20;else if(pairAgeSec<=900)score+=15;else if(pairAgeSec<=3600)score+=10;else if(pairAgeSec<=10800)score+=4}
    if(buys>=50)score+=15;else if(buys>=20)score+=12;else if(buys>=5)score+=7;else if(buys>0)score+=3;
    if(ratio>=2)score+=12;else if(ratio>=1.3)score+=8;else if(ratio>=1)score+=4;
    if(vol5>=100000)score+=10;else if(vol5>=25000)score+=7;else if(vol5>=5000)score+=3;
    score=clamp(score,0,100);
    const prev=prevByMint.get(x.mint)||{};
    const baseIsMint=p?.baseToken?.address===x.mint;
    candidates.push({
      mint:x.mint,
      symbol:baseIsMint?(p?.baseToken?.symbol||prev.symbol||null):(prev.symbol||null),
      name:baseIsMint?(p?.baseToken?.name||prev.name||null):(prev.name||null),
      sources:[...x.sources],
      firstSeenAt:prev.firstSeenAt||new Date().toISOString(),
      lastSeenAt:new Date().toISOString(),
      pairAddress:p?.pairAddress||null,
      dexId:p?.dexId||null,
      pairCreatedAt:Number.isFinite(createdMs)?new Date(createdMs).toISOString():null,
      pairAgeSec:pairAgeSec==null?null:Number(pairAgeSec.toFixed(2)),
      liquidityUsd:liq,
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
  const out={
    version:'3.12.0',
    updatedAt:new Date().toISOString(),
    status:healthySources>=2?'HEALTHY':'DEGRADED',
    healthySources,
    failedSources:feeds.length-healthySources,
    failures,
    currentFeedMints:sourceMap.size,
    candidates:candidates.slice(0,100),
    policy:'DISCOVERY_ONLY_NEVER_GRANTS_ENTRY'
  };
  atomic(STATE,out);atomic(OUT,out);
  console.log(`NEW_LISTING_RADAR status=${out.status} feedMints=${out.currentFeedMints} candidates=${out.candidates.length} topScore=${out.candidates[0]?.preScore??0}`);
} finally {
  try{if(lockFd!==null)fs.closeSync(lockFd)}catch{}
  try{fs.unlinkSync(LOCK)}catch{}
}
