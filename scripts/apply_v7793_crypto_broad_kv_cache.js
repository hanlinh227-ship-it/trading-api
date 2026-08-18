const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing '+label+' start');const b=s.indexOf(end,a);if(b<0)throw new Error('Missing '+label+' end');s=s.slice(0,a)+repl+s.slice(b);}
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}
s=s.replaceAll('V77.9.2','V77.9.3').replaceAll('Trading V77.9.2 Adaptive Symbol Intelligence Hub','Trading V77.9.3 Adaptive Symbol Intelligence Hub');
mustReplace('newsPrefix: "v779:news_clear:",','newsPrefix: "v779:news_clear:",\n    cryptoBroadCache: "v779:crypto_broad_cache",','crypto cache key');
const block=`async function loadCryptoBroadCache(env,maxAgeMs=120000){
  const out=new Map();try{const p=await env.TRADING_STATE?.get(CONFIG.keys.cryptoBroadCache,"json");for(const row of p?.rows||[]){if(!row?.symbol||!row?.quote||!Number.isFinite(Number(row.cachedAt)))continue;if(Date.now()-Number(row.cachedAt)>maxAgeMs)continue;out.set(norm(row.symbol),{...row.quote,broadCached:true,broadCachedAt:Number(row.cachedAt)});}}catch{}return out;
}
async function saveCryptoBroadCache(env,map){
  try{const rows=[];for(const [symbol,quote] of map){if(!CRYPTO.includes(norm(symbol))||!quote?.price)continue;rows.push({symbol:norm(symbol),quote,cachedAt:Number(quote.broadCachedAt)||Date.now()});}await env.TRADING_STATE?.put(CONFIG.keys.cryptoBroadCache,JSON.stringify({savedAt:Date.now(),rows}),{expirationTtl:300});}catch{}
}
async function cryptoBroadMap(symbols,env){
  let map=await cryptoBulk().catch(()=>new Map());
  const providers=[bybitQuote,okxQuote,binanceQuote];
  if(map.size<Math.min(55,symbols.length)){
    for(let pass=0;pass<2&&map.size<Math.min(55,symbols.length);pass++){
      if(pass>0)await new Promise(r=>setTimeout(r,850));
      for(const fn of providers){const missing=symbols.filter(x=>!map.has(x));if(!missing.length)break;let alive=false;try{const q=await fn('BTCUSDT');alive=!!q?.price;if(alive)map.set('BTCUSDT',q);}catch{}if(!alive)continue;const exact=await quotePool(missing,fn,pass===0?4:3);for(const [k,v] of exact)map.set(k,v);if(map.size>=Math.min(55,symbols.length))break;await new Promise(r=>setTimeout(r,180));}
    }
  }
  for(const [k,q] of map)if(!q.broadCachedAt)map.set(k,{...q,broadCachedAt:Date.now()});
  const cached=await loadCryptoBroadCache(env);for(const [k,q] of cached)if(!map.has(k))map.set(k,q);
  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();await saveCryptoBroadCache(env,map);if(map.size)await new Promise(r=>setTimeout(r,600));return map;
}
`;
replaceRange('async function cryptoBroadMap(symbols){','function changeFromCandles(',block,'cryptoBroadMap');
mustReplace('const bulk=await cryptoBroadMap(symbols),btc=bulk.get("BTCUSDT")?.percentChange??0;','const bulk=await cryptoBroadMap(symbols,env),btc=bulk.get("BTCUSDT")?.percentChange??0;','broad env');
fs.writeFileSync(path,s,'utf8');console.log('Applied V77.9.3 persistent crypto broad cache');
