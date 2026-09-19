const KEY='bybit:marketcap:top100:v1';
const TTL_MS=30*60*1000;
const STALE_MAX_MS=24*60*60*1000;
const TOP_N=100;
const STABLE_BASES=new Set(['USDT','USDC','USDE','DAI','FDUSD','TUSD','USDD','PYUSD','FRAX','USDP','GUSD','LUSD','USD1','USD0']);
const WRAPPED_PREFIXES=['WETH','WBTC','WBNB','WSTETH','STETH'];

const num=v=>Number.isFinite(Number(v))?Number(v):0;
async function get(env,key,d={}){try{return await env.TRADING_STATE?.get(key,{type:'json'})??d}catch{return d}}
async function put(env,key,x){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(x))}catch{}}

function cleanSymbol(v=''){return String(v||'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');}
function eligibleBase(base=''){
  const b=cleanSymbol(base);
  return b&&!STABLE_BASES.has(b)&&!WRAPPED_PREFIXES.includes(b);
}

export async function loadTop100MarketCapUniverse(env){
  const now=Date.now(),cached=await get(env,KEY,{});
  if(Array.isArray(cached.rows)&&cached.rows.length>=50&&now-num(cached.at)<TTL_MS)return {...cached,cached:true,stale:false};
  try{
    const url='https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h';
    const res=await fetch(url,{headers:{accept:'application/json','user-agent':'trading-api-top100-marketcap/1.0'},signal:AbortSignal.timeout(8000)});
    if(!res.ok)throw new Error('COINGECKO_HTTP_'+res.status);
    const raw=await res.json();
    if(!Array.isArray(raw)||raw.length<70)throw new Error('COINGECKO_TOP100_INCOMPLETE');
    const seen=new Set(),rows=[];
    for(const x of raw){
      const base=cleanSymbol(x.symbol);
      if(!eligibleBase(base)||seen.has(base))continue;
      seen.add(base);
      rows.push({base,id:String(x.id||''),name:String(x.name||''),rank:num(x.market_cap_rank),marketCapUsd:num(x.market_cap),volume24hUsd:num(x.total_volume),priceUsd:num(x.current_price),change24hPct:num(x.price_change_percentage_24h)});
    }
    rows.sort((a,b)=>a.rank-b.rank||b.marketCapUsd-a.marketCapUsd);
    const out={at:now,source:'COINGECKO_MARKET_CAP_TOP100',topN:TOP_N,rows:rows.slice(0,TOP_N),stale:false};
    await put(env,KEY,out);return out;
  }catch(e){
    if(Array.isArray(cached.rows)&&cached.rows.length>=50&&now-num(cached.at)<STALE_MAX_MS)return {...cached,cached:true,stale:true,error:String(e?.message||e).slice(0,180)};
    return {at:now,source:'COINGECKO_MARKET_CAP_TOP100',topN:TOP_N,rows:[],stale:true,error:String(e?.message||e).slice(0,180),failClosed:true};
  }
}

export function top100Map(state={}){
  return new Map((state.rows||[]).map(x=>[cleanSymbol(x.base),x]));
}

export const BYBIT_MARKET_CAP_UNIVERSE_VERSION='BYBIT_MARKET_CAP_TOP100_V1';
