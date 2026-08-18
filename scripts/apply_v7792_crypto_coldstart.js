const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing '+label+' start');const b=s.indexOf(end,a);if(b<0)throw new Error('Missing '+label+' end');s=s.slice(0,a)+repl+s.slice(b);}
s=s.replaceAll('V77.9.1','V77.9.2').replaceAll('Trading V77.9.1 Adaptive Symbol Intelligence Hub','Trading V77.9.2 Adaptive Symbol Intelligence Hub');
const block=`async function cryptoBroadMap(symbols){
  let map=await cryptoBulk().catch(()=>new Map());
  if(map.size>=Math.min(45,symbols.length))return map;
  const providers=[bybitQuote,okxQuote,binanceQuote];
  for(let pass=0;pass<2&&map.size<Math.min(55,symbols.length);pass++){
    if(pass>0)await new Promise(r=>setTimeout(r,900));
    for(const fn of providers){
      const missing=symbols.filter(x=>!map.has(x));if(!missing.length)break;
      let alive=false;try{const q=await fn('BTCUSDT');alive=!!q?.price;if(alive)map.set('BTCUSDT',q);}catch{}
      if(!alive)continue;
      const exact=await quotePool(missing,fn,pass===0?4:3);for(const [k,v] of exact)map.set(k,v);
      if(map.size>=Math.min(55,symbols.length))break;
      await new Promise(r=>setTimeout(r,220));
    }
  }
  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();
  if(map.size)await new Promise(r=>setTimeout(r,650));
  return map;
}
`;
replaceRange('async function cryptoBroadMap(symbols){','function changeFromCandles(',block,'cryptoBroadMap');
fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.9.2 crypto cold-start stabilization');
