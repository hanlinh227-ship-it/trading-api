const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing '+label+' start');const b=s.indexOf(end,a);if(b<0)throw new Error('Missing '+label+' end');s=s.slice(0,a)+repl+s.slice(b);}
s=s.replaceAll('V77.9.3','V77.9.4').replaceAll('Trading V77.9.3 Adaptive Symbol Intelligence Hub','Trading V77.9.4 Adaptive Symbol Intelligence Hub');
const block=`async function kucoinAllTickers(){
  const r=await fetchTimeout("https://api.kucoin.com/api/v1/market/allTickers"),p=await r.json().catch(()=>null);if(!r.ok||p?.code!=="200000"||!Array.isArray(p?.data?.ticker))throw new Error("KuCoin bulk unavailable");return p.data.ticker;
}
async function gateAllTickers(){
  const r=await fetchTimeout("https://api.gateio.ws/api/v4/spot/tickers",{headers:{Accept:"application/json"}}),p=await r.json().catch(()=>null);if(!r.ok||!Array.isArray(p))throw new Error("Gate bulk unavailable");return p;
}
async function cryptoBulk(){
  if(memory.cryptoBulk&&Date.now()-memory.cryptoBulkAt<5000)return memory.cryptoBulk;
  const [bb,ox,bn,kc,gt]=await Promise.allSettled([
    bybit("/v5/market/tickers",{category:"spot"}),
    okx("/api/v5/market/tickers",{instType:"SPOT"}),
    (async()=>{for(const host of ["https://data-api.binance.vision","https://api.binance.com"]){try{const r=await fetchTimeout(host+"/api/v3/ticker/24hr");if(!r.ok)throw new Error(String(r.status));return await r.json();}catch{}}return [];})(),
    kucoinAllTickers(),gateAllTickers()
  ]);
  const map=new Map();
  if(bb.status==="fulfilled")for(const r of bb.value?.result?.list||[]){const sym=norm(r.symbol);if(CRYPTO.includes(sym))map.set(sym,{source:"Bybit Spot",price:num(r.lastPrice),open:num(r.prevPrice24h),high:num(r.highPrice24h),low:num(r.lowPrice24h),percentChange:num(r.price24hPcnt)!==null?num(r.price24hPcnt)*100:null,fresh:true});}
  if(ox.status==="fulfilled")for(const r of ox.value?.data||[]){const sym=norm(r.instId);if(CRYPTO.includes(sym)&&!map.has(sym)){const price=num(r.last),open=num(r.open24h);map.set(sym,{source:"OKX Spot",price,open,high:num(r.high24h),low:num(r.low24h),percentChange:price&&open?((price-open)/open)*100:null,fresh:true});}}
  if(bn.status==="fulfilled"&&Array.isArray(bn.value))for(const r of bn.value){const sym=norm(r.symbol);if(CRYPTO.includes(sym)&&!map.has(sym))map.set(sym,{source:"Binance Spot",price:num(r.lastPrice),open:num(r.openPrice),high:num(r.highPrice),low:num(r.lowPrice),percentChange:num(r.priceChangePercent),fresh:true});}
  if(kc.status==="fulfilled")for(const r of kc.value){const sym=norm(r.symbol);if(!CRYPTO.includes(sym)||map.has(sym))continue;const price=num(r.last),chg=num(r.changeRate),open=price&&chg!==null&&1+chg!==0?price/(1+chg):null;map.set(sym,{source:"KuCoin Spot Broad",price,open,high:num(r.high),low:num(r.low),percentChange:chg!==null?chg*100:null,fresh:true,analysisOnly:true});}
  if(gt.status==="fulfilled")for(const r of gt.value){const sym=norm(r.currency_pair);if(!CRYPTO.includes(sym)||map.has(sym))continue;const price=num(r.last),pct=num(r.change_percentage);const open=price&&pct!==null&&1+pct/100!==0?price/(1+pct/100):null;map.set(sym,{source:"Gate Spot Broad",price,open,high:num(r.high_24h),low:num(r.low_24h),percentChange:pct,fresh:true,analysisOnly:true});}
  for(const [k,v] of [...map])if(!v?.price||v.price<=0)map.delete(k);
  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();return map;
}
`;
replaceRange('async function cryptoBulk(){','function ema(',block,'cryptoBulk');
fs.writeFileSync(path,s,'utf8');console.log('Applied V77.9.4 diversified crypto bulk discovery');
