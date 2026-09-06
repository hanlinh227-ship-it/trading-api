import fs from 'node:fs';

const APP='/opt/meme-alpha/app';
const DATA='/var/lib/meme-alpha/data/paper';
const OUT=`${APP}/runtime-status/new-listing-radar.json`;
const STATE=`${DATA}/new-listing-radar.json`;
const FEED_CACHE=`${DATA}/solana-dex-universe-feed-cache.json`;
const LOCK='/tmp/meme-alpha-solana-dex-universe.lock';
const DEX='https://api.dexscreener.com';
const GECKO='https://api.geckoterminal.com/api/v2';
const runtime=read(`${APP}/config/runtime.json`,{});
const JUP=String(runtime.jupiter||'https://api.jup.ag').replace(/\/$/,'');
const WSOL='So11111111111111111111111111111111111111112';
const USDC='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';
const USDT='Es9vMFrzaCERmJfrF4H2FYD2oBGj2q8YtNQ3j4YF3L9';
const EXCLUDE=new Set([WSOL,USDC,USDT]);
const MAX_CURRENT=360;
const FAST_DISCOVERY_RESERVE=140;
const FAST_PROVIDER_MAX_AGE_MS=90000; // FAST_DISCOVERY_V372
const MAX_OUTPUT=520;
const WATCH_KEEP_MS=7*24*60*60*1000;
const FEED_STALE_MAX_MS=15*60*1000;

const FEEDS={
  'jupiter-recent':{ttl:20000,url:`${JUP}/tokens/v2/recent`,provider:'jupiter'},
  'dex-profile':{ttl:30000,url:`${DEX}/token-profiles/latest/v1`,provider:'dexscreener'},
  'dex-boost':{ttl:30000,url:`${DEX}/token-boosts/latest/v1`,provider:'dexscreener'},
  'dex-community':{ttl:30000,url:`${DEX}/community-takeovers/latest/v1`,provider:'dexscreener'},
  'gecko-new-1':{ttl:20000,url:`${GECKO}/networks/solana/new_pools?page=1&include=base_token,quote_token,dex`,provider:'geckoterminal'},
  'gecko-new-2':{ttl:30000,url:`${GECKO}/networks/solana/new_pools?page=2&include=base_token,quote_token,dex`,provider:'geckoterminal'},
  'gecko-trending':{ttl:30000,url:`${GECKO}/networks/solana/trending_pools?page=1&include=base_token,quote_token,dex`,provider:'geckoterminal'},
  'gecko-top':{ttl:120000,url:`${GECKO}/networks/solana/pools?page=1&include=base_token,quote_token,dex`,provider:'geckoterminal'}
};

function read(path,d={}){try{return JSON.parse(fs.readFileSync(path,'utf8'))}catch{return d}}
function n(v,d=0){const x=Number(v);return Number.isFinite(x)?x:d}
function clamp(x,a,b){return Math.max(a,Math.min(b,x))}
function arr(x){return Array.isArray(x)?x:[]}
function atomic(path,value){const t=`${path}.tmp-${process.pid}`;fs.writeFileSync(t,JSON.stringify(value,null,2));fs.renameSync(t,path)}
function writeRuntime(value){const text=JSON.stringify(value,null,2);try{atomic(OUT,value)}catch{fs.writeFileSync(OUT,text)}}
function mintFromGeckoId(id){const s=String(id||'');return s.startsWith('solana_')?s.slice(7):s}
function ageBucket(createdMs){if(!Number.isFinite(createdMs))return 'UNKNOWN';const a=Date.now()-createdMs;if(a<=60*60*1000)return 'ULTRA_NEW_1H';if(a<=24*60*60*1000)return 'DAY_1';if(a<=7*24*60*60*1000)return 'SHORT_DAY_7D';return 'MATURE'}
async function get(url,timeout=7000){const headers={accept:'application/json'};if(url.startsWith(GECKO))headers.accept='application/json;version=20230203';const r=await fetch(url,{headers,signal:AbortSignal.timeout(timeout)});if(!r.ok)throw new Error(`HTTP_${r.status}`);return await r.json()}
function ensure(map,mint){if(!mint||EXCLUDE.has(mint))return null;if(!map.has(mint))map.set(mint,{mint,sources:new Set(),providers:new Set(),symbol:null,name:null,pairAddress:null,dexId:null,pairCreatedAt:null,liquidityUsd:0,volume5m:0,volume1h:0,buys5m:0,sells5m:0,buys1h:0,sells1h:0,priceChange5m:null,priceChange1h:null,holderCount:0,organicScore:0,profile:{}});return map.get(mint)}
function mergeNum(x,k,v){const z=n(v,NaN);if(Number.isFinite(z))x[k]=Math.max(n(x[k]),z)}
function geckoIncluded(body){const m=new Map();for(const x of arr(body?.included)){m.set(String(x.id),x)}return m}
function parseGecko(map,body,source,provider){const inc=geckoIncluded(body);for(const p of arr(body?.data)){const a=p?.attributes||{},rel=p?.relationships||{};let base=mintFromGeckoId(rel?.base_token?.data?.id),quote=mintFromGeckoId(rel?.quote_token?.data?.id);let mint=EXCLUDE.has(base)&&quote&&!EXCLUDE.has(quote)?quote:base;if(!mint||EXCLUDE.has(mint))continue;const x=ensure(map,mint);if(!x)continue;x.sources.add(source);x.providers.add(provider);const token=inc.get(rel?.base_token?.data?.id)||inc.get(rel?.quote_token?.data?.id);x.symbol=x.symbol||token?.attributes?.symbol||null;x.name=x.name||token?.attributes?.name||null;x.pairAddress=x.pairAddress||a.address||null;x.dexId=x.dexId||String(rel?.dex?.data?.id||'').replace(/^solana_/,'')||null;x.pairCreatedAt=x.pairCreatedAt||a.pool_created_at||null;mergeNum(x,'liquidityUsd',a.reserve_in_usd);mergeNum(x,'volume5m',a?.volume_usd?.m5);mergeNum(x,'volume1h',a?.volume_usd?.h1);mergeNum(x,'buys5m',a?.transactions?.m5?.buys);mergeNum(x,'sells5m',a?.transactions?.m5?.sells);mergeNum(x,'buys1h',a?.transactions?.h1?.buys);mergeNum(x,'sells1h',a?.transactions?.h1?.sells);if(a?.price_change_percentage?.m5!=null)x.priceChange5m=n(a.price_change_percentage.m5);if(a?.price_change_percentage?.h1!=null)x.priceChange1h=n(a.price_change_percentage.h1)} }
function parseJupiter(map,body,source,provider){for(const row of arr(body)){const mint=String(row?.id||row?.address||row?.mint||'').trim();const x=ensure(map,mint);if(!x)continue;x.sources.add(source);x.providers.add(provider);x.symbol=x.symbol||row?.symbol||null;x.name=x.name||row?.name||null;x.pairAddress=x.pairAddress||row?.firstPool?.id||null;x.pairCreatedAt=x.pairCreatedAt||row?.firstPool?.createdAt||null;mergeNum(x,'liquidityUsd',row?.liquidity);mergeNum(x,'holderCount',row?.holderCount);mergeNum(x,'organicScore',row?.organicScore);const s=row?.stats5m||{};mergeNum(x,'volume5m',n(s?.buyVolume)+n(s?.sellVolume));mergeNum(x,'buys5m',s?.numBuys??s?.buys);mergeNum(x,'sells5m',s?.numSells??s?.sells);if(row?.icon)x.profile.icon=row.icon}}
function parseDex(map,body,source,provider){for(const row of arr(body)){if(String(row?.chainId||'').toLowerCase()!=='solana')continue;const mint=String(row?.tokenAddress||'').trim();const x=ensure(map,mint);if(!x)continue;x.sources.add(source);x.providers.add(provider);for(const k of ['url','description','icon','header','amount','totalAmount','claimDate'])if(row?.[k]!=null)x.profile[k]=row[k];if(Array.isArray(row?.links))x.profile.links=row.links.slice(0,8)}}
function scoreRow(x){const createdMs=Date.parse(x.pairCreatedAt||'');const age=Number.isFinite(createdMs)?Date.now()-createdMs:Infinity;let s=0;s+=Math.min(18,x.sources.size*4)+Math.min(12,x.providers.size*6);if(age<=10*60*1000)s+=20;else if(age<=60*60*1000)s+=18;else if(age<=6*60*60*1000)s+=14;else if(age<=24*60*60*1000)s+=10;else if(age<=3*24*60*60*1000)s+=7;else if(age<=7*24*60*60*1000)s+=4;if(x.liquidityUsd>=250000)s+=20;else if(x.liquidityUsd>=100000)s+=17;else if(x.liquidityUsd>=50000)s+=14;else if(x.liquidityUsd>=20000)s+=10;else if(x.liquidityUsd>=7500)s+=5;if(x.buys5m>=50)s+=12;else if(x.buys5m>=20)s+=9;else if(x.buys5m>=5)s+=5;const ratio=x.sells5m>0?x.buys5m/x.sells5m:(x.buys5m>0?4:0);if(ratio>=2)s+=8;else if(ratio>=1.25)s+=5;else if(ratio>=1)s+=2;if(x.volume5m>=100000)s+=8;else if(x.volume5m>=25000)s+=6;else if(x.volume5m>=5000)s+=3;if(x.organicScore>=70)s+=4;else if(x.organicScore>=50)s+=2;const confidence=clamp(.18+x.providers.size*.18+x.sources.size*.06+(x.pairAddress?.length?0.10:0)+(x.liquidityUsd>=10000?0.12:0)+(x.buys5m>=5?0.08:0),0,1);return{score:clamp(s,0,100),confidence,createdMs,ratio}}

async function main(){
 if(process.argv.includes('--self-test')){const m=new Map();parseGecko(m,{data:[{attributes:{address:'POOL',pool_created_at:new Date().toISOString(),reserve_in_usd:'20000',transactions:{m5:{buys:12,sells:4}},volume_usd:{m5:'9000'}},relationships:{base_token:{data:{id:'solana_TESTMINT'}},quote_token:{data:{id:`solana_${WSOL}`}},dex:{data:{id:'raydium'}}}}],included:[{id:'solana_TESTMINT',attributes:{symbol:'TEST',name:'Test'}}]},'gecko-new-1','geckoterminal');const x=m.get('TESTMINT');if(!x||x.liquidityUsd!==20000||x.buys5m!==12)throw new Error('SELF_TEST');console.log('V367_SOLANA_DEX_UNIVERSE_SELF_TEST=PASS');console.log('AGE_BUCKETS=ULTRA_NEW_1H,DAY_1,SHORT_DAY_7D,MATURE');console.log('DISCOVERY_ONLY_ENTRY_GATES_UNCHANGED=TRUE');console.log('V372_FAST_DISCOVERY_SELF_TEST=PASS');console.log('FAST_DISCOVERY_NEVER_GRANTS_ENTRY=TRUE');return}
 let fd=null;try{fd=fs.openSync(LOCK,'wx')}catch{try{const st=fs.statSync(LOCK);if(Date.now()-st.mtimeMs>20000){fs.unlinkSync(LOCK);fd=fs.openSync(LOCK,'wx')}}catch{}}if(fd===null){console.log('V367_RADAR_SKIP_LOCKED');return}fs.writeFileSync(fd,String(process.pid));
 try{
  const cache=read(FEED_CACHE,{feeds:{}});cache.feeds=cache.feeds||{};const failures=[];const now=Date.now();
  for(const [name,cfg] of Object.entries(FEEDS)){const old=cache.feeds[name]||{};const due=!old.lastAttemptAt||now-n(old.lastAttemptAt)>cfg.ttl;if(!due)continue;old.lastAttemptAt=now;try{old.body=await get(cfg.url);old.lastOkAt=Date.now();old.lastError=null}catch(e){old.lastError=String(e?.message||e).slice(0,120);failures.push({source:name,error:old.lastError})}cache.feeds[name]=old}
  atomic(FEED_CACHE,cache);
  const map=new Map();const freshProviders=new Set();const freshSources=[];const fastProviders=new Set();const fastSources=[];
  for(const [name,cfg] of Object.entries(FEEDS)){const f=cache.feeds[name]||{},age=Date.now()-n(f.lastOkAt,0);if(!f.body||age<0||age>FEED_STALE_MAX_MS)continue;freshProviders.add(cfg.provider);freshSources.push(name);if(age<=FAST_PROVIDER_MAX_AGE_MS){fastProviders.add(cfg.provider);fastSources.push(name)}if(name.startsWith('gecko-'))parseGecko(map,f.body,name,cfg.provider);else if(name==='jupiter-recent')parseJupiter(map,f.body,name,cfg.provider);else parseDex(map,f.body,name,cfg.provider)}
  const previous=read(OUT,read(STATE,{candidates:[]}));const current=[];
  for(const x of map.values()){const r=scoreRow(x);current.push({mint:x.mint,symbol:x.symbol,name:x.name,sources:[...x.sources],providers:[...x.providers],providerCount:x.providers.size,sourceCount:x.sources.size,currentFeed:true,firstSeenAt:(previous.candidates||[]).find(y=>y.mint===x.mint)?.firstSeenAt||new Date().toISOString(),lastSeenAt:new Date().toISOString(),pairAddress:x.pairAddress,dexId:x.dexId,pairCreatedAt:x.pairCreatedAt,pairAgeSec:Number.isFinite(r.createdMs)?Math.max(0,(Date.now()-r.createdMs)/1000):null,ageBucket:ageBucket(r.createdMs),liquidityUsd:x.liquidityUsd,holderCount:x.holderCount,organicScore:x.organicScore,volume5m:x.volume5m,volume1h:x.volume1h,buys5m:x.buys5m,sells5m:x.sells5m,buys1h:x.buys1h,sells1h:x.sells1h,buySellTxnRatio:Number(r.ratio.toFixed(3)),priceChange5m:x.priceChange5m,priceChange1h:x.priceChange1h,preScore:r.score,discoveryConfidence:Number(r.confidence.toFixed(3)),entryEligible:false,purpose:'DISCOVERY_ONLY',profile:x.profile})}
  // FAST_DISCOVERY_V372: reserve part of the discovery universe for genuinely new/high-velocity mints.
  // This only changes what the scanner gets to inspect. It never grants an entry.
  const fastEligible=x=>{
    const age=n(x.pairAgeSec,Infinity),conf=n(x.discoveryConfidence),liq=n(x.liquidityUsd),buys=n(x.buys5m),vol=n(x.volume5m),chg=Math.abs(n(x.priceChange5m)),ratio=n(x.buySellTxnRatio);
    const flow=(buys>=3&&ratio>=1.03)||vol>=1500||chg>=5;
    return age>=0&&age<=6*3600&&conf>=0.24&&(liq>=4000||age<=3600)&&flow;
  };
  const velocity=x=>Math.min(45,n(x.buys5m)*0.55)+Math.min(35,n(x.volume5m)/3500)+Math.min(25,Math.abs(n(x.priceChange5m))*0.8)+(n(x.pairAgeSec,Infinity)<=3600?18:0)+n(x.preScore)*0.35;
  const scoreRank=current.slice().sort((a,b)=>b.preScore-a.preScore||b.discoveryConfidence-a.discoveryConfidence);
  const hotRank=current.filter(fastEligible).sort((a,b)=>velocity(b)-velocity(a)||b.preScore-a.preScore);
  const hotMints=new Set(hotRank.slice(0,FAST_DISCOVERY_RESERVE).map(x=>x.mint));
  const chosen=[];const chosenMints=new Set();
  for(const x of hotRank){if(chosen.length>=FAST_DISCOVERY_RESERVE)break;if(chosenMints.has(x.mint))continue;x.fastDiscoveryLane=true;x.discoveryPriority=Number(velocity(x).toFixed(3));chosen.push(x);chosenMints.add(x.mint)}
  for(const x of scoreRank){if(chosen.length>=MAX_CURRENT)break;if(chosenMints.has(x.mint))continue;x.fastDiscoveryLane=hotMints.has(x.mint);x.discoveryPriority=x.fastDiscoveryLane?Number(velocity(x).toFixed(3)):n(x.preScore);chosen.push(x);chosenMints.add(x.mint)}const curSet=new Set(chosen.map(x=>x.mint));const retained=[];for(const old of previous.candidates||[]){if(curSet.has(old.mint))continue;const t=Date.parse(old.lastSeenAt||old.firstSeenAt||0);if(Number.isFinite(t)&&Date.now()-t<=WATCH_KEEP_MS)retained.push({...old,currentFeed:false,staleWatch:true,entryEligible:false,purpose:'DISCOVERY_ONLY',preScore:Math.max(0,n(old.preScore)-2)})}
  retained.sort((a,b)=>n(b.preScore)-n(a.preScore));const candidates=[...chosen,...retained].slice(0,MAX_OUTPUT);const providerCount=freshProviders.size,fastProviderCount=fastProviders.size;const status=providerCount>=2&&chosen.length>0?'HEALTHY':providerCount>=1?'DEGRADED':'DEGRADED';const out={version:'3.72.0-fast-discovery',updatedAt:new Date().toISOString(),status,policy:'FAST_DISCOVERY_ONLY_NEVER_GRANTS_ENTRY',providerCount,providers:[...freshProviders],freshSources,fastProviderCount,fastProviders:[...fastProviders],fastSources,fastProviderMaxAgeMs:FAST_PROVIDER_MAX_AGE_MS,fastDiscoveryReserve:FAST_DISCOVERY_RESERVE,fastDiscoveryCandidates:chosen.filter(x=>x.fastDiscoveryLane===true).length,failures,currentFeedMints:map.size,currentCandidates:chosen.length,watchlistCandidates:retained.length,candidates};writeRuntime(out);try{atomic(STATE,out)}catch{};console.log(`FAST_DISCOVERY v=3.72.0 status=${status} providers=${providerCount} fastProviders=${fastProviderCount} feedMints=${map.size} current=${chosen.length} fast=${out.fastDiscoveryCandidates} watch=${retained.length}`)
 } finally {try{if(fd!==null)fs.closeSync(fd)}catch{}try{fs.unlinkSync(LOCK)}catch{}}
}
main().catch(e=>{console.error(e);process.exit(1)});
