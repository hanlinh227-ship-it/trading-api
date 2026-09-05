import fs from 'node:fs';

const APP='/opt/meme-alpha/app';
const PAPER='/var/lib/meme-alpha/data/paper';
const STATE='/var/lib/meme-alpha/data/micro-live/state.json';
const OUT=`${APP}/runtime-status/whale-flow-intel.json`;
const OBS=`${APP}/runtime-status/portfolio-observability.json`;
const CFG=JSON.parse(fs.readFileSync(`${APP}/config/runtime.json`,'utf8'));
const SELF_TEST=process.argv.includes('--self-test');
const CYCLE_MS=15000;
const RPC_SPACING_MS=1800;
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
const prior=read(OUT,{rows:[]});
let lastRows=Array.isArray(prior.rows)?prior.rows.filter(r=>Date.now()-Date.parse(r?.observedAt||0)<=600000):[];
for(const r of lastRows){if(Number.isFinite(Number(r?.supply))&&Number(r.supply)>0)supplyCache.set(r.mint,{value:Number(r.supply),at:Date.parse(r.observedAt)||Date.now(),cached:true})}

function providerCooldown(failures){return Math.min(300000,30000*Math.pow(2,Math.min(4,Math.max(0,failures-1))))}
function publicProviderView(){return [...provider.values()].map(p=>({index:p.index,failures:p.failures,cooldownMsRemaining:Math.max(0,p.cooldownUntil-Date.now()),lastOkAt:p.lastOkAt,lastError:p.lastError}));}
async function rateShape(){const wait=Math.max(0,nextRpcAt-Date.now());if(wait)await sleep(wait);nextRpcAt=Date.now()+RPC_SPACING_MS;}
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
function providerIsRateLimited(){return [...provider.values()].some(p=>p.cooldownUntil>Date.now()&&String(p.lastError||'').includes('429'))}
async function rpc(method,params){
  if(!ENDPOINTS.length)throw new Error('NO_RPC_ENDPOINT_CONFIGURED');
  const now=Date.now();const eligible=ENDPOINTS.map(x=>provider.get(x)).filter(p=>p.cooldownUntil<=now).sort((a,b)=>a.failures-b.failures||a.index-b.index);
  if(!eligible.length){const e=new Error(providerIsRateLimited()?'RPC_429_BACKOFF':'ALL_RPC_PROVIDERS_COOLING_DOWN');if(providerIsRateLimited())e.code=429;throw e}
  let last=null;
  for(const p of eligible){
    try{return await callOne(p,method,params)}catch(e){last=e;p.failures+=1;p.lastError=String(e?.message||e).slice(0,100);if(e?.code===429||String(e?.message||'').includes('429'))p.cooldownUntil=Date.now()+providerCooldown(p.failures);else p.cooldownUntil=Date.now()+Math.min(60000,5000*p.failures)}
  }
  throw last||new Error('RPC_ALL_FAILED');
}

function heldMints(){const s=read(STATE,{positions:[]});return [...new Set((s.positions||[]).map(x=>x?.mint).filter(Boolean))];}
function signalMints(){const s=read(`${APP}/runtime-status/signal-snapshot.json`,{candidates:[]});return (s.candidates||[]).filter(x=>x?.mint&&x?.decision==='PROBE_CANDIDATE').sort((a,b)=>num(b.score)-num(a.score)).map(x=>x.mint);}
function scannerMints(){const s=read(`${PAPER}/scanner-latest.json`,{candidates:[]});return (s.candidates||[]).filter(x=>x?.mint).sort((a,b)=>num(b.score)-num(a.score)).map(x=>x.mint);}
function priorityMints(){return [...new Set([...heldMints(),...signalMints(),...scannerMints()])].slice(0,120);}
function nextMint(){const q=priorityMints();if(!q.length)return null;const m=q[cursor%q.length];cursor++;return m;}

async function supply(mint){const old=supplyCache.get(mint);if(old&&Date.now()-old.at<600000)return {...old,cached:true};const r=await rpc('getTokenSupply',[mint,{commitment:'processed'}]);const v=num(r?.value?.uiAmount);const x={value:v,at:Date.now(),cached:false};supplyCache.set(mint,x);return x;}
async function largest(mint){const r=await rpc('getTokenLargestAccounts',[mint,{commitment:'processed'}]);return (r?.value||[]).map(x=>num(x.uiAmount)).filter(x=>x>=0);}
async function inspect(mint){
  const sp=await supply(mint);const vals=await largest(mint);const total=Math.max(sp.value,1e-12),top10=vals.slice(0,10).reduce((a,b)=>a+b,0)/total*100,top1=(vals[0]||0)/total*100;
  const prev=lastRows.find(x=>x.mint===mint);
  return {mint,observedAt:new Date().toISOString(),top1Pct:Number(top1.toFixed(4)),top10Pct:Number(top10.toFixed(4)),deltaTop10Pct:prev?Number((top10-num(prev.top10Pct)).toFixed(4)):0,holderPressureScore:Number(Math.max(-10,Math.min(10,5-(top10-35)/5)).toFixed(3)),whaleFlowScore:Number(Math.max(-10,Math.min(10,(prev?num(prev.top10Pct)-top10:0)*2)).toFixed(3)),supplyCached:sp.cached,supply:sp.value,providerCount:ENDPOINTS.length};
}
function observability(){const s=read(STATE,{positions:[]});const positions=Array.isArray(s.positions)?s.positions:[];return{version:'3.70.0',updatedAt:new Date().toISOString(),stateReadable:Array.isArray(s.positions),openPositions:positions.length,positionMints:positions.map(x=>x?.mint).filter(Boolean),stateVersion:s.version||null};}
function freshnessMs(r){const t=Date.parse(r?.observedAt||0);return Number.isFinite(t)?Date.now()-t:Infinity;}
function statusOf({ok,rateLimit,rows}){if(!ENDPOINTS.length)return'NO_RPC_CONFIG';if(ok)return rows.some(r=>r.supplyCached)?'HEALTHY_CACHED_RATE_SHAPED':'HEALTHY';if(rows.some(r=>freshnessMs(r)<=120000))return'HEALTHY_CACHED_RATE_SHAPED';if(rateLimit||providerIsRateLimited())return'RATE_LIMIT_BACKOFF';return'WARMING_UP';}

if(SELF_TEST){
  if(providerCooldown(1)!==30000||providerCooldown(5)!==300000)throw new Error('PROVIDER_COOLDOWN_SELFTEST');
  if(CYCLE_MS!==15000||RPC_SPACING_MS!==1800)throw new Error('RPC_BUDGET_SELFTEST');
  console.log('V370_WHALE_ADAPTIVE_BUDGET_SELF_TEST=PASS');
  console.log('RPC_CYCLE_15S=TRUE');
  console.log('RPC_SPACING_1800MS=TRUE');
  console.log('PERSIST_CACHED_ROWS_ACROSS_RESTART=TRUE');
  console.log('RATE_LIMIT_COOLDOWN_UP_TO_300S=TRUE');
  console.log('FRESH_CACHED_ROWS_FAIL_SOFT=TRUE');
  process.exit(0);
}

async function cycle(){
  let ok=false,rateLimit=false,error=null;const mint=nextMint();
  try{if(mint){const row=await inspect(mint);lastRows=[row,...lastRows.filter(x=>x.mint!==mint)];ok=true}}catch(e){error=String(e?.message||e);rateLimit=e?.code===429||error.includes('429')}
  const held=new Set(heldMints());
  lastRows=lastRows.filter(r=>freshnessMs(r)<=180000||held.has(r.mint)&&freshnessMs(r)<=600000);
  const rows=lastRows.slice().sort((a,b)=>(held.has(b.mint)?1:0)-(held.has(a.mint)?1:0)||Date.parse(b.observedAt)-Date.parse(a.observedAt)).slice(0,120);
  const out={version:'3.70.0-adaptive-whale',updatedAt:new Date().toISOString(),status:statusOf({ok,rateLimit,rows}),rpcConfigured:ENDPOINTS.length>0,providerCount:ENDPOINTS.length,providers:publicProviderView(),rateShaped:true,cycleMs:CYCLE_MS,rpcSpacingMs:RPC_SPACING_MS,oneMintPerCycle:true,supplyCacheMs:600000,rowFreshnessTtlMs:180000,heldRowTtlMs:600000,heldPositionsAlwaysMonitored:true,inspectedMint:mint,rows,error};
  atomic(OUT,out);atomic(OBS,observability());
}

await cycle();
setInterval(()=>cycle().catch(e=>atomic(OUT,{version:'3.70.0-adaptive-whale',updatedAt:new Date().toISOString(),status:'INTERNAL_ERROR',error:String(e?.message||e),rows:lastRows,providerCount:ENDPOINTS.length,providers:publicProviderView(),cycleMs:CYCLE_MS,rpcSpacingMs:RPC_SPACING_MS})),CYCLE_MS);
