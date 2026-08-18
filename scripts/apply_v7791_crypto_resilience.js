const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function insertBefore(marker,text,label){const i=s.indexOf(marker);if(i<0)throw new Error('Missing '+label);s=s.slice(0,i)+text+s.slice(i);}
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

s=s.replaceAll('V77.9.0','V77.9.1').replaceAll('Trading V77.9.0 Adaptive Symbol Intelligence Hub','Trading V77.9.1 Adaptive Symbol Intelligence Hub');

const resilient=`async function quotePool(symbols,fn,concurrency=6){
  const out=new Map(),list=[...symbols],state={i:0};
  async function worker(){while(state.i<list.length){const idx=state.i++,sym=list[idx];try{const q=await fn(sym);if(q?.price&&q.fresh!==false)out.set(sym,q);}catch{}await new Promise(r=>setTimeout(r,35));}}
  await Promise.all(Array.from({length:Math.min(concurrency,list.length||1)},()=>worker()));return out;
}
async function cryptoBroadMap(symbols){
  let map=await cryptoBulk().catch(()=>new Map());
  if(map.size>=Math.min(20,symbols.length))return map;
  const providers=[bybitQuote,okxQuote,binanceQuote];
  for(const fn of providers){
    const missing=symbols.filter(x=>!map.has(x));if(!missing.length)break;
    let alive=false;try{const q=await fn('BTCUSDT');alive=!!q?.price;if(alive)map.set('BTCUSDT',q);}catch{}
    if(!alive)continue;
    const exact=await quotePool(missing,fn,6);for(const [k,v] of exact)map.set(k,v);
    if(map.size>=symbols.length)break;
  }
  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();return map;
}
`;
insertBefore('function changeFromCandles(',resilient,'context marker');

mustReplace('const bulk=await cryptoBulk().catch(()=>new Map()),btc=bulk.get("BTCUSDT")?.percentChange??0;','const bulk=await cryptoBroadMap(symbols),btc=bulk.get("BTCUSDT")?.percentChange??0;','crypto broad resilient map');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.9.1 resilient exact crypto discovery');
