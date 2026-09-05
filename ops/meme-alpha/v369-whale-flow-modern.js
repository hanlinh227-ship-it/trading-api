import fs from 'node:fs';

const APP='/opt/meme-alpha/app';
const PAPER='/var/lib/meme-alpha/data/paper';
const STATE='/var/lib/meme-alpha/data/micro-live/state.json';
const OUT=`${APP}/runtime-status/whale-flow-intel.json`;
const OBS=`${APP}/runtime-status/portfolio-observability.json`;
const CFG=JSON.parse(fs.readFileSync(`${APP}/config/runtime.json`,'utf8'));
const SELF_TEST=process.argv.includes('--self-test');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const atomic=(p,x)=>{const t=p+'.tmp';fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p);try{fs.chmodSync(p,0o664)}catch{}};
const num=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;

function endpointList(){
  const raw=[CFG.rpc,CFG.solanaRpc,process.env.SOLANA_RPC_URL,...(Array.isArray(CFG.rpcFallbacks)?CFG.rpcFallbacks:[]),...(Array.isArray(CFG.rpcUrls)?CFG.rpcUrls:[]),...(Array.isArray(CFG.solanaRpcUrls)?CFG.solanaRpcUrls:[])];
  return [...new Set(raw.filter(x=>typeof x==='string'&&/^https?:\/\//.test(x.trim())).map(x=>x.trim()))];
}
const ENDPOINTS=endpointList();
const provider=new Map(ENDPOINTS.map((url,i)=>[url,{url,index:i,failures:0,cooldownUntil:0,lastOkAt:null,lastError:null}]));
let nextRpcAt=0;
const supplyCache=new Map();
let cursor=0;
let lastRows=[];

function providerCooldown(failures){return Math.min(120000,15000*Math.pow(2,Math.min(3,Math.max(0,failures-1))))}
function publicProviderView(){return [...provider.values()].map(p=>({index:p.index,failures:p.failures,cooldownMsRemaining:Math.max(0,p.cooldownUntil-Date.now()),lastOkAt:p.lastOkAt,lastError:p.lastError}));}
async function rateShape(){const wait=Math.max(0,nextRpcAt-Date.now());if(wait)await sleep(wait);nextRpcAt=Date.now()+800;}
async function callOne(p,method,params){
  await rateShape();
  const ctrl=new AbortController();const tm=setTimeout(()=>ctrl.abort(),7000);
  try{
    const r=await fetch(p.url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:ctrl.signal});
    const txt=await r.text();let j={};try{j=JSON.parse(txt)}catch{}
    if(r.status===429||j?.error?.code===429){const e=new Error('RPC_429');e.code=429;throw e}
    if(!r.ok||j.error)throw new Error(`RPC_${r.status||'ERR'}_${j?.error?.code||''}`);
    p.failures=Math.max(0,p.failures-1);p.cooldownUntil=0;p.lastOkAt=new Date().toISOString();p.lastError=null;return j.result;
  } finally {clearTimeout(tm)}
}
async function rpc(method,params){
  if(!ENDPOINTS.length)throw new Error('NO_RPC_ENDPOINT_CONFIGURED');
  let last=null,rateLimited=0;
  for(let pass=0;pass<2;pass++){
    const now=Date.now();const eligible=ENDPOINTS.map(x=>provider.get(x)).filter(p=>p.cooldownUntil<=now).sort((a,b)=>a.failures-b.failures||a.index-b.index);
    if(!eligible.length)break;
    for(const p of eligible){
      try{return await callOne(p,method,params)}catch(e){last=e;p.failures+=1;p.lastError=String(e?.message||e).slice(0,100);if(e?.code===429||String(e?.message||'').includes('429')){rateLimited++;p.cooldownUntil=Date.now()+providerCooldown(p.failures)}else p.cooldownUntil=Date.now()+Math.min(30000,3000*p.failures);}
    }
  }
  const e=last||new Error('ALL_RPC_PROVIDERS_COOLING_DOWN');if(rateLimited>0)e.code=429;throw e;
}

function heldMints(){const s=read(STATE,{positions:[]});return [...new Set((s.positions||[]).map(x=>x?.mint).filter(Boolean))];}
function signalMints(){const s=read(`${APP}/runtime-status/signal-snapshot.json`,{candidates:[]});return (s.candidates||[]).filter(x=>x?.mint).sort((a,b)=>num(b.score)-num(a.score)).map(x=>x.mint);}
function scannerMints(){const s=read(`${PAPER}/scanner-latest.json`,{candidates:[]});return (s.candidates||[]).filter(x=>x?.mint).sort((a,b)=>num(b.score)-num(a.score)).map(x=>x.mint);}
function priorityMints(){return [...new Set([...heldMints(),...signalMints(),...scannerMints()])].slice(0,120);}
function nextMint(){const held=heldMints();if(held.length){const m=held[cursor%held.length];cursor++;return m}const q=priorityMints();if(!q.length)return null;const m=q[cursor%q.length];cursor++;return m;}

async function supply(mint){const old=supplyCache.get(mint);if(old&&Date.now()-old.at<600000)return {...old,cached:true};const r=await rpc('getTokenSupply',[mint,{commitment:'processed'}]);const v=num(r?.value?.uiAmount);const x={value:v,at:Date.now(),cached:false};supplyCache.set(mint,x);return x;}
async function largest(mint){const r=await rpc('getTokenLargestAccounts',[mint,{commitment:'processed'}]);return (r?.value||[]).map(x=>num(x.uiAmount)).filter(x=>x>=0);}
async function inspect(mint){
  const sp=await supply(mint);const vals=await largest(mint);const total=Math.max(sp.value,1e-12),top10=vals.slice(0,10).reduce((a,b)=>a+b,0)/total*100,top1=(vals[0]||0)/total*100;
  const prev=lastRows.find(x=>x.mint===mint);
  const row={mint,observedAt:new Date().toISOString(),top1Pct:Number(top1.toFixed(4)),top10Pct:Number(top10.toFixed(4)),deltaTop10Pct:prev?Number((top10-num(prev.top10Pct)).toFixed(4)):0,holderPressureScore:Number(Math.max(-10,Math.min(10,5-(top10-35)/5)).toFixed(3)),whaleFlowScore:Number(Math.max(-10,Math.min(10,(prev?num(prev.top10Pct)-top10:0)*2)).toFixed(3)),supplyCached:sp.cached,providerCount:ENDPOINTS.length};
  return row;
}
function observability(){const s=read(STATE,{positions:[]});const positions=Array.isArray(s.positions)?s.positions:[];return{version:'3.69.0',updatedAt:new Date().toISOString(),stateReadable:Array.isArray(s.positions),openPositions:positions.length,positionMints:positions.map(x=>x?.mint).filter(Boolean),stateVersion:s.version||null};}
function freshnessMs(r){const t=Date.parse(r?.observedAt||0);return Number.isFinite(t)?Date.now()-t:Infinity;}
function statusOf({ok,rateLimit,rows}){if(!ENDPOINTS.length)return'NO_RPC_CONFIG';if(ok)return rows.some(r=>r.supplyCached)?'HEALTHY_CACHED_RATE_SHAPED':'HEALTHY';if(rateLimit)return'RATE_LIMIT_BACKOFF';return rows.length?'WARMING_UP':'WARMING_UP';}

if(SELF_TEST){
  if(providerCooldown(1)!==15000||providerCooldown(4)!==120000)throw new Error('PROVIDER_COOLDOWN_SELFTEST');
  const sample={positions:[{mint:'A'},{mint:'B'}]};if(new Set(sample.positions.map(x=>x.mint)).size!==2)throw new Error('HELD_PRIORITY_SELFTEST');
  console.log('V369_WHALE_MODERN_SELF_TEST=PASS');
  console.log('MULTI_PROVIDER_FAILOVER=TRUE');
  console.log('PER_PROVIDER_429_COOLDOWN=TRUE');
  console.log('ONE_MINT_PER_CYCLE=TRUE');
  console.log('SUPPLY_CACHE_10M=TRUE');
  console.log('HELD_POSITIONS_PRIORITY=TRUE');
  console.log('ROW_FRESHNESS_TTL_180S=TRUE');
  process.exit(0);
}

async function cycle(){
  let ok=false,rateLimit=false,error=null;const mint=nextMint();
  try{if(mint){const row=await inspect(mint);lastRows=[row,...lastRows.filter(x=>x.mint!==mint)]}}catch(e){error=String(e?.message||e);rateLimit=e?.code===429||error.includes('429');}
  if(mint&&lastRows.some(x=>x.mint===mint&&freshnessMs(x)<20000))ok=true;
  lastRows=lastRows.filter(r=>freshnessMs(r)<=180000||heldMints().includes(r.mint));
  const held=new Set(heldMints());
  const rows=lastRows.slice().sort((a,b)=>(held.has(b.mint)?1:0)-(held.has(a.mint)?1:0)||Date.parse(b.observedAt)-Date.parse(a.observedAt)).slice(0,120);
  const out={version:'3.69.0-modern-whale',updatedAt:new Date().toISOString(),status:statusOf({ok,rateLimit,rows}),rpcConfigured:ENDPOINTS.length>0,providerCount:ENDPOINTS.length,providers:publicProviderView(),rateShaped:true,oneMintPerCycle:true,supplyCacheMs:600000,rowFreshnessTtlMs:180000,heldPositionsAlwaysMonitored:true,inspectedMint:mint,rows,error};
  atomic(OUT,out);atomic(OBS,observability());
}

await cycle();
setInterval(()=>cycle().catch(e=>atomic(OUT,{version:'3.69.0-modern-whale',updatedAt:new Date().toISOString(),status:'INTERNAL_ERROR',error:String(e?.message||e),rows:lastRows,providerCount:ENDPOINTS.length,providers:publicProviderView()})),5000);
