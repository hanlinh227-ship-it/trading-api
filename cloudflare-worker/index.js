import V73_CONFIG from "../data/nocut_intraday_allpass_v73.json" with { type: "json" };

const CONFIG = {
  version: "V77.8.0",
  service: "Trading V77.8.0 Unified Canonical Hub",
  tdCreditsPerMinute: 55,
  tdReserveCredits: 3,
  maxQuoteAgeSec: 65,
  cryptoQuoteAgeSec: 10,
  fetchTimeoutMs: 6500,
  scanDeadlineMs: 42000,
  candleOutputSize: 120,
  maxCandidates: 3,
  maxMarketActive: 3,
  maxLimitActive: 3,
  maxPendingLimit: 3,
  maxWatch: 3,
  defaultRiskUsd: 250,
  minM5DisplacementATR: 0.50,
  minRoomR: 1.0,
  rr2RoomRequired: 2.2,
  maxExecutionCostR: 0.10,
  pendingLimitExpiryMinutes: 90,
  runLockTtlSec: 55,
  newsClearanceTtlSec: 1800,
  keys: {
    books: "v775:books",
    history: "v775:history",
    lastRun: "v775:last_run",
    runLock: "v775:run_lock",
    newsPrefix: "v778:news_clear:",
  },
};

const FOREX = [
  "AUDCAD","AUDCHF","AUDJPY","AUDNZD","AUDUSD","CADCHF","CADJPY","CHFJPY",
  "EURAUD","EURCAD","EURCHF","EURGBP","EURJPY","EURNZD","EURUSD",
  "GBPAUD","GBPCAD","GBPCHF","GBPJPY","GBPNZD","GBPUSD",
  "NZDCAD","NZDCHF","NZDJPY","NZDUSD","USDCAD","USDCHF","USDJPY"
];
const CRYPTO_BASE = [
  "BTC","ETH","SOL","HYPE","SHIB","TRX","XRP","AAVE","ADA","ALGO","APT","ARB","ATOM","AVAX",
  "BCH","BONK","CRV","DOGE","DOT","ETC","FIL","FLOKI","HBAR","INJ","JTO","JUP","KAITO","LDO","LINK",
  "LTC","MOODENG","NEAR","ONDO","OP","ORDI","PENGU","PEPE","PNUT","POL","POPCAT","RENDER","S","STX",
  "SUI","TAO","TIA","TON","TRUMP","UNI","WIF","WLD","AIXBT","ASTER","FARTCOIN","GRASS","IP","LIT",
  "PUMP","VIRTUAL","XPL","ZEC"
];
const CRYPTO = CRYPTO_BASE.map(x => `${x}USDT`);
const METALS = ["XAUUSD","XAGUSD"];
const GROUPS = { forex: FOREX, crypto: CRYPTO, metal: METALS };
const INTERVALS = ["5min","15min","1h","4h","1day"];
const memory = { tdCreditsLeft: null, cryptoBulk: null, cryptoBulkAt: 0 };

const nowSec = () => Math.floor(Date.now()/1000);
const num = v => { const n = Number(v); return Number.isFinite(n) ? n : null; };
const norm = s => String(s || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
const json = (body,status=200) => new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8"}});
function marketType(symbol){const s=norm(symbol);if(FOREX.includes(s))return "forex";if(CRYPTO.includes(s))return "crypto";if(METALS.includes(s))return "metal";return "unknown";}
function tdSymbol(symbol){const s=norm(symbol),t=marketType(s);if(t==="forex"||t==="metal")return `${s.slice(0,3)}/${s.slice(3)}`;return s;}
function parseTs(v){if(v==null)return null;if(typeof v==="number")return v>2e10?Math.floor(v/1000):Math.floor(v);if(/^\d+$/.test(String(v))){const n=Number(v);return n>2e10?Math.floor(n/1000):Math.floor(n);}const d=Date.parse(String(v).replace(" ","T")+(/Z|[+-]\d\d:?\d\d$/.test(String(v))?"":"Z"));return Number.isFinite(d)?Math.floor(d/1000):null;}
async function fetchTimeout(url,init={},ms=CONFIG.fetchTimeoutMs){const c=new AbortController(),id=setTimeout(()=>c.abort("timeout"),ms);try{return await fetch(url,{...init,signal:c.signal});}finally{clearTimeout(id);}}

async function tdFetch(endpoint,params,env){
  if(!env.TWELVE_DATA_API_KEY)throw new Error("TWELVE_DATA_API_KEY missing");
  const q=new URLSearchParams(params);q.set("apikey",env.TWELVE_DATA_API_KEY);
  const r=await fetchTimeout(`https://api.twelvedata.com/${endpoint}?${q}`);
  const left=num(r.headers.get("api-credits-left"));if(left!==null)memory.tdCreditsLeft=left;
  let p;try{p=await r.json();}catch{throw new Error(`Twelve Data JSON HTTP ${r.status}`);}
  if(!r.ok||p?.status==="error"||p?.code)throw new Error(p?.message||`Twelve Data HTTP ${r.status}`);
  return p;
}
function findNumericField(obj,names){if(!obj||typeof obj!=="object")return null;for(const [k,v] of Object.entries(obj)){if(names.includes(String(k).toLowerCase())){const n=num(v);if(n!==null)return n;}if(v&&typeof v==="object"){const n=findNumericField(v,names);if(n!==null)return n;}}return null;}
async function tdQuotaStatus(env){
  if(!env.TWELVE_DATA_API_KEY)return {left:0,error:"TWELVE_DATA_API_KEY missing"};
  const q=new URLSearchParams({apikey:env.TWELVE_DATA_API_KEY}),r=await fetchTimeout(`https://api.twelvedata.com/api_usage?${q}`);
  const p=await r.json().catch(()=>null);
  let left=num(r.headers.get("api-credits-left"));if(left===null)left=findNumericField(p,["api_credits_left","credits_left","remaining_credits","credits_remaining","remaining"]);
  if(left===null&&r.status===429)left=0;if(left!==null)memory.tdCreditsLeft=left;
  return {left,status:r.status};
}
function tdPlannedCost(group){return group==="forex"?40:group==="metal"?10:0;}
function tdRetryAfterSec(){return Math.max(3,62-(Math.floor(Date.now()/1000)%60));}
async function ensureTdBudget(group,env){
  const required=tdPlannedCost(group);
  if(required===0)return {ok:true,required:0,left:memory.tdCreditsLeft};
  const q=await tdQuotaStatus(env);
  if(q.left!==null&&q.left<required+CONFIG.tdReserveCredits)return {ok:false,required,left:q.left,retryAfterSec:tdRetryAfterSec()};
  return {ok:true,required,left:q.left};
}
function candleSec(interval){return {"5min":300,"15min":900,"1h":3600,"4h":14400,"1day":86400}[interval]||0;}
function normalizeCandles(rows,sec){
  const t=nowSec();
  return (rows||[]).map(r=>({timestamp:Number(r.timestamp),open:Number(r.open),high:Number(r.high),low:Number(r.low),close:Number(r.close),volume:num(r.volume)}))
    .filter(c=>c.timestamp&&Number.isFinite(c.open)&&Number.isFinite(c.high)&&Number.isFinite(c.low)&&Number.isFinite(c.close)&&(!sec||c.timestamp+sec<=t))
    .sort((a,b)=>a.timestamp-b.timestamp);
}
function tdCandlesFromNode(node,interval){
  const n=node?.data?.values?node.data:node;if(!Array.isArray(n?.values))return null;
  return normalizeCandles(n.values.map(v=>({timestamp:parseTs(v.datetime),open:v.open,high:v.high,low:v.low,close:v.close,volume:v.volume})),candleSec(interval));
}
async function tdBatchCandles(symbols,interval,env,outputsize=CONFIG.candleOutputSize){
  const requested=[...new Set(symbols.map(norm))],provider=requested.map(tdSymbol),out=new Map();if(!requested.length)return out;
  const p=await tdFetch("time_series",{symbol:provider.join(","),interval,outputsize:String(outputsize),order:"ASC",timezone:"UTC"},env);
  if(Array.isArray(p?.values)){const c=tdCandlesFromNode(p,interval);if(c)out.set(requested[0],c);return out;}
  const lookup=new Map(provider.map((x,i)=>[norm(x),requested[i]]));
  for(const [key,raw] of Object.entries(p||{})){
    const node=raw?.data?.values?raw.data:raw,c=tdCandlesFromNode(raw,interval);if(!c)continue;
    const canonical=lookup.get(norm(node?.meta?.symbol||key));if(canonical)out.set(canonical,c);
  }
  return out;
}
async function tdQuote(symbol,env){
  const ps=tdSymbol(symbol),p=await tdFetch("quote",{symbol:ps},env),price=num(p.close)??num(p.price);
  if(!price||price<=0)throw new Error("TD price invalid");
  const ts=parseTs(p.last_quote_at??p.timestamp??p.datetime),age=ts==null?null:Math.max(0,nowSec()-ts);
  return {source:"Twelve Data",requestedSymbol:norm(symbol),providerSymbol:ps,price,providerTimestamp:ts,quoteAgeSec:age,fresh:age!==null&&age<=CONFIG.maxQuoteAgeSec,bid:null,ask:null,executionVerified:false,analysisOnly:true};
}

async function bybit(path,params={}){
  const q=new URLSearchParams(params),r=await fetchTimeout(`https://api.bybit.com${path}?${q}`),p=await r.json().catch(()=>null);
  if(!r.ok||!p||Number(p.retCode)!==0)throw new Error(p?.retMsg||`Bybit ${r.status}`);return p;
}
async function okx(path,params={}){
  const q=new URLSearchParams(params),r=await fetchTimeout(`https://www.okx.com${path}?${q}`),p=await r.json().catch(()=>null);
  if(!r.ok||!p||p.code!=="0")throw new Error(p?.msg||`OKX ${r.status}`);return p;
}
function okxId(symbol){const s=norm(symbol);if(!s.endsWith("USDT"))throw new Error("not USDT");return `${s.slice(0,-4)}-USDT`;}
async function bybitQuote(symbol){
  const s=norm(symbol),p=await bybit("/v5/market/tickers",{category:"spot",symbol:s}),r=p?.result?.list?.[0];
  if(!r||norm(r.symbol)!==s)throw new Error("Bybit exact symbol absent");
  const price=num(r.lastPrice),bid=num(r.bid1Price),ask=num(r.ask1Price),ts=Math.floor(Number(p.time)/1000),age=Math.max(0,nowSec()-ts);
  if(!price)throw new Error("Bybit invalid price");
  return {source:"Bybit Spot",providerSymbol:s,price,bid,ask,providerTimestamp:ts,quoteAgeSec:age,fresh:age<=CONFIG.cryptoQuoteAgeSec,executionVerified:bid!==null&&ask!==null&&ask>=bid,open:num(r.prevPrice24h),high:num(r.highPrice24h),low:num(r.lowPrice24h),percentChange:num(r.price24hPcnt)!==null?num(r.price24hPcnt)*100:null};
}
async function okxQuote(symbol){
  const s=norm(symbol),id=okxId(s),p=await okx("/api/v5/market/ticker",{instId:id}),r=p?.data?.[0];
  if(!r||norm(r.instId)!==s)throw new Error("OKX exact symbol absent");
  const price=num(r.last),bid=num(r.bidPx),ask=num(r.askPx),ts=Math.floor(Number(r.ts)/1000),age=Math.max(0,nowSec()-ts);
  if(!price)throw new Error("OKX invalid price");
  return {source:"OKX Spot",providerSymbol:id,price,bid,ask,providerTimestamp:ts,quoteAgeSec:age,fresh:age<=CONFIG.cryptoQuoteAgeSec,executionVerified:bid!==null&&ask!==null&&ask>=bid,open:num(r.open24h),high:num(r.high24h),low:num(r.low24h),percentChange:num(r.open24h)&&price?((price-num(r.open24h))/num(r.open24h))*100:null};
}
async function binanceQuote(symbol){
  const s=norm(symbol);let last=null;
  for(const host of ["https://data-api.binance.vision","https://api.binance.com"]){
    try{
      const r=await fetchTimeout(`${host}/api/v3/ticker/24hr?symbol=${encodeURIComponent(s)}`),p=await r.json();
      if(!r.ok)throw new Error(p?.msg||`Binance ${r.status}`);
      const price=num(p.lastPrice),bid=num(p.bidPrice),ask=num(p.askPrice),ts=Math.floor(Number(p.closeTime)/1000),age=Math.max(0,nowSec()-ts);
      if(!price)throw new Error("Binance invalid price");
      return {source:"Binance Spot",providerSymbol:s,price,bid,ask,providerTimestamp:ts,quoteAgeSec:age,fresh:age<=CONFIG.cryptoQuoteAgeSec,executionVerified:bid!==null&&ask!==null&&ask>=bid,open:num(p.openPrice),high:num(p.highPrice),low:num(p.lowPrice),percentChange:num(p.priceChangePercent)};
    }catch(e){last=e;}
  }
  throw last||new Error("Binance unavailable");
}
function bybitInterval(i){return {"5min":"5","15min":"15","1h":"60","4h":"240","1day":"D"}[i];}
function okxInterval(i){return {"5min":"5m","15min":"15m","1h":"1H","4h":"4H","1day":"1Dutc"}[i];}
function binanceInterval(i){return {"5min":"5m","15min":"15m","1h":"1h","4h":"4h","1day":"1d"}[i];}
async function bybitCandles(symbol,interval){
  const p=await bybit("/v5/market/kline",{category:"spot",symbol:norm(symbol),interval:bybitInterval(interval),limit:String(CONFIG.candleOutputSize)});
  return normalizeCandles((p?.result?.list||[]).map(x=>({timestamp:Math.floor(Number(x[0])/1000),open:x[1],high:x[2],low:x[3],close:x[4],volume:x[5]})),candleSec(interval));
}
async function okxCandles(symbol,interval){
  const p=await okx("/api/v5/market/candles",{instId:okxId(symbol),bar:okxInterval(interval),limit:String(CONFIG.candleOutputSize)});
  return normalizeCandles((p?.data||[]).filter(x=>String(x[8]??"1")==="1").map(x=>({timestamp:Math.floor(Number(x[0])/1000),open:x[1],high:x[2],low:x[3],close:x[4],volume:x[5]})),candleSec(interval));
}
async function binanceCandles(symbol,interval){
  const s=norm(symbol),iv=binanceInterval(interval);let last=null;
  for(const host of ["https://data-api.binance.vision","https://api.binance.com"]){
    try{
      const r=await fetchTimeout(`${host}/api/v3/klines?symbol=${encodeURIComponent(s)}&interval=${iv}&limit=${CONFIG.candleOutputSize}`),p=await r.json();
      if(!r.ok||!Array.isArray(p))throw new Error(p?.msg||`Binance ${r.status}`);
      return normalizeCandles(p.map(x=>({timestamp:Math.floor(Number(x[0])/1000),open:x[1],high:x[2],low:x[3],close:x[4],volume:x[5]})),candleSec(interval));
    }catch(e){last=e;}
  }
  throw last||new Error("Binance candles unavailable");
}
async function cryptoDeepBundle(symbol){
  const s=norm(symbol),venues=[
    {name:"Bybit Spot",quote:bybitQuote,candles:bybitCandles},
    {name:"OKX Spot",quote:okxQuote,candles:okxCandles},
    {name:"Binance Spot",quote:binanceQuote,candles:binanceCandles},
  ],errors=[];
  for(const v of venues){
    try{
      const [quote,...candles]=await Promise.all([v.quote(s),...INTERVALS.map(i=>v.candles(s,i))]);
      if(candles.some(c=>!Array.isArray(c)||c.length<55))throw new Error("insufficient closed candles");
      return {source:v.name,quote,candles};
    }catch(e){errors.push(`${v.name}: ${e?.message||String(e)}`);}
  }
  throw new Error(`No exact exchange deep bundle: ${errors.join(" | ")}`);
}
async function cryptoExecutionQuote(symbol){
  const errors=[];for(const fn of [bybitQuote,okxQuote,binanceQuote]){try{return await fn(symbol);}catch(e){errors.push(e?.message||String(e));}}
  throw new Error(`exact venue unavailable: ${errors.join(" | ")}`);
}
async function cryptoBulk(){
  if(memory.cryptoBulk&&Date.now()-memory.cryptoBulkAt<5000)return memory.cryptoBulk;
  const [bb,ox,bn]=await Promise.allSettled([
    bybit("/v5/market/tickers",{category:"spot"}),
    okx("/api/v5/market/tickers",{instType:"SPOT"}),
    (async()=>{for(const host of ["https://data-api.binance.vision","https://api.binance.com"]){try{const r=await fetchTimeout(`${host}/api/v3/ticker/24hr`);if(!r.ok)throw new Error(String(r.status));return await r.json();}catch{}}return [];})()
  ]);
  const map=new Map();
  if(bb.status==="fulfilled")for(const r of bb.value?.result?.list||[]){const s=norm(r.symbol);if(CRYPTO.includes(s))map.set(s,{source:"Bybit Spot",price:num(r.lastPrice),open:num(r.prevPrice24h),high:num(r.highPrice24h),low:num(r.lowPrice24h),percentChange:num(r.price24hPcnt)!==null?num(r.price24hPcnt)*100:null,fresh:true});}
  if(ox.status==="fulfilled")for(const r of ox.value?.data||[]){const s=norm(r.instId);if(CRYPTO.includes(s)&&!map.has(s)){const price=num(r.last),open=num(r.open24h);map.set(s,{source:"OKX Spot",price,open,high:num(r.high24h),low:num(r.low24h),percentChange:price&&open?((price-open)/open)*100:null,fresh:true});}}
  if(bn.status==="fulfilled"&&Array.isArray(bn.value))for(const r of bn.value){const s=norm(r.symbol);if(CRYPTO.includes(s)&&!map.has(s))map.set(s,{source:"Binance Spot",price:num(r.lastPrice),open:num(r.openPrice),high:num(r.highPrice),low:num(r.lowPrice),percentChange:num(r.priceChangePercent),fresh:true});}
  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();return map;
}

function ema(values,n){if(values.length<n)return null;const k=2/(n+1);let e=values.slice(0,n).reduce((a,b)=>a+b,0)/n;for(const v of values.slice(n))e=v*k+e*(1-k);return e;}
function atr(c,n=14){if(c.length<n+1)return null;const tr=[];for(let i=1;i<c.length;i++)tr.push(Math.max(c[i].high-c[i].low,Math.abs(c[i].high-c[i-1].close),Math.abs(c[i].low-c[i-1].close)));return tr.slice(-n).reduce((a,b)=>a+b,0)/n;}
function rsi(vals,n=14){if(vals.length<n+1)return null;let g=0,l=0;for(let i=vals.length-n;i<vals.length;i++){const d=vals[i]-vals[i-1];if(d>0)g+=d;else l-=d;}if(l===0)return 100;const rs=(g/n)/(l/n);return 100-100/(1+rs);}
const high=c=>c.length?Math.max(...c.map(x=>x.high)):null,low=c=>c.length?Math.min(...c.map(x=>x.low)):null;
function tf(c){
  if(!Array.isArray(c)||c.length<55)return {ready:false};
  const closes=c.map(x=>x.close),last=c.at(-1),prev=c.at(-2),e20=ema(closes,20),e50=ema(closes,50),a=atr(c),rr=rsi(closes);
  let trend="NEUTRAL";if(last.close>e20&&e20>e50)trend="BULLISH";if(last.close<e20&&e20<e50)trend="BEARISH";
  const hist=c.slice(0,-1),lh=high(hist.slice(-20)),ll=low(hist.slice(-20));
  return {ready:true,timestamp:last.timestamp,open:last.open,high:last.high,low:last.low,close:last.close,ema20:e20,ema50:e50,atr14:a,rsi14:rr,trend,liquidityHigh20:lh,liquidityLow20:ll,bullishBreak:lh!==null&&last.close>lh,bearishBreak:ll!==null&&last.close<ll,bullishReclaim:last.low<prev.low&&last.close>prev.close,bearishReclaim:last.high>prev.high&&last.close<prev.close};
}
function m15Location(c,T,side){
  if(c.length<16||!T.ready)return {valid:false,type:"NO_LOCATION",level:null};
  const last=c.at(-1),prev=c.at(-2),prior=c.slice(-14,-2),ph=high(prior),pl=low(prior),e=T.ema20;
  if(side==="LONG"){
    if(pl!==null&&last.low<pl&&last.close>pl)return {valid:true,type:"LIQUIDITY_SWEEP_RECLAIM",level:pl};
    if(ph!==null&&prev.close>ph&&last.low<=ph&&last.close>ph)return {valid:true,type:"BREAKOUT_RETEST",level:ph};
    if(e&&last.low<=e&&last.close>e&&last.close>last.open)return {valid:true,type:"CLEAN_RECLAIM",level:e};
  }else{
    if(ph!==null&&last.high>ph&&last.close<ph)return {valid:true,type:"LIQUIDITY_SWEEP_RECLAIM",level:ph};
    if(pl!==null&&prev.close<pl&&last.high>=pl&&last.close<pl)return {valid:true,type:"BREAKOUT_RETEST",level:pl};
    if(e&&last.high>=e&&last.close<e&&last.close<last.open)return {valid:true,type:"CLEAN_RECLAIM",level:e};
  }
  return {valid:false,type:"NO_LOCATION",level:null};
}
function m5Trigger(c,T,side){
  if(c.length<12||!T.ready||!T.atr14)return {valid:false};
  const ret=c.at(-1),disp=c.at(-2),prior=c.slice(-9,-2),ph=high(prior),pl=low(prior),body=Math.abs(disp.close-disp.open),d=body>=CONFIG.minM5DisplacementATR*T.atr14;
  if(side==="LONG"){const m=ph!==null&&disp.close>ph,rt=ph!==null&&ret.low<=ph&&ret.close>ph&&ret.close>=ret.open;return {valid:m&&d&&rt,mss:m,displacement:d,retest:rt,level:ph};}
  const m=pl!==null&&disp.close<pl,rt=pl!==null&&ret.high>=pl&&ret.close<pl&&ret.close<=ret.open;return {valid:m&&d&&rt,mss:m,displacement:d,retest:rt,level:pl};
}
function v73Prior(symbol,type){
  let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=norm(symbol).replace(/USDT$/,"");if(!key)return {applicable:false,available:false};
  const e=V73_CONFIG?.[type]?.symbols?.[key];if(!e)return {applicable:true,available:false,key};
  const m=e.method||{},st=m.style||{};
  return {applicable:true,available:true,key,source:e.source,timeframe:e.timeframe,status:m.status,family:st.family||m.profile||(m.router?"ROUTER":null),entryMode:st.entryMode||(m.router?"ROUTER":null),rr:st.rr??null,classification:V73_CONFIG.classification};
}
function watch(symbol,type,side,reason,extra={}){return {ok:true,status:"WATCH",action:"WATCH",symbol,market:type,side,reason,canonicalStage:reason,engine:CONFIG.version,...extra};}
async function getNewsClearance(symbol,env){
  const s=norm(symbol),key=`${CONFIG.keys.newsPrefix}${s}`;
  try{const raw=await env.TRADING_STATE?.get(key,"json");if(raw?.clearedAt&&Date.now()-Number(raw.clearedAt)<=CONFIG.newsClearanceTtlSec*1000)return raw;}catch{}
  if(env.NEWS_GATE_URL){
    try{const u=new URL(env.NEWS_GATE_URL);u.searchParams.set("symbol",s);u.searchParams.set("market",marketType(s));const r=await fetchTimeout(u.toString());const p=await r.json();if(r.ok&&p?.clear===true){const v={clearedAt:Date.now(),source:"NEWS_GATE_URL",detail:p.detail||null};await env.TRADING_STATE?.put(key,JSON.stringify(v),{expirationTtl:CONFIG.newsClearanceTtlSec});return v;}}catch{}
  }
  return null;
}
async function setNewsClearance(symbol,env){const s=norm(symbol),v={clearedAt:Date.now(),source:"TELEGRAM_MANUAL"};await env.TRADING_STATE?.put(`${CONFIG.keys.newsPrefix}${s}`,JSON.stringify(v),{expirationTtl:CONFIG.newsClearanceTtlSec});return v;}
function buildTradePlan(side,entry,M5,M15,H1,pendingRetest){
  const floor=M5.atr14*.8,structure=side==="LONG"?Math.min(M5.liquidityLow20??entry-floor,M15.liquidityLow20??entry-floor):Math.max(M5.liquidityHigh20??entry+floor,M15.liquidityHigh20??entry+floor);
  const sl=side==="LONG"?Math.min(structure,entry-floor):Math.max(structure,entry+floor),risk=Math.abs(entry-sl);if(!Number.isFinite(risk)||risk<=0)return null;
  const opp=side==="LONG"?H1.liquidityHigh20:H1.liquidityLow20,roomR=opp===null?null:Math.abs(opp-entry)/risk;
  if(roomR===null||roomR<CONFIG.minRoomR)return {invalid:"H1_CLEAN_ROOM_REQUIRED",roomR};
  const targetRR=roomR>=CONFIG.rr2RoomRequired?2:1;
  return {entry,sl,risk,roomR,targetRR,tp1:side==="LONG"?entry+risk:entry-risk,tp2:side==="LONG"?entry+risk*2:entry-risk*2,mode:pendingRetest?"LIMIT":"MARKET"};
}
async function deepAnalyze(symbol,env,candles=null,reference=null,source=null){
  const s=norm(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};
  const prior=v73Prior(s,type);
  try{
    if(!candles){
      if(type==="crypto"){const b=await cryptoDeepBundle(s);candles=b.candles;reference=b.quote;source=b.source;}
      else candles=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env).then(m=>m.get(s)||[])));
    }
  }catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"ANALYSIS_DATA_UNAVAILABLE",error:e?.message||String(e)};}
  const [m5c,m15c,h1c,h4c,d1c]=candles||[],[M5,M15,H1,H4,D1]=(candles||[]).map(tf);
  if(!M5||[M5,M15,H1,H4,D1].some(x=>!x?.ready))return watch(s,type,"NEUTRAL","TIMEFRAME_DATA_REQUIRED",{source,canonical:{v73Prior:prior}});
  const long=D1.trend==="BULLISH"&&H4.trend==="BULLISH"&&H1.trend==="BULLISH",short=D1.trend==="BEARISH"&&H4.trend==="BEARISH"&&H1.trend==="BEARISH";
  if(!long&&!short)return watch(s,type,"NEUTRAL","HTF_ALIGNMENT_REQUIRED",{source,canonical:{v73Prior:prior}});
  const side=long?"LONG":"SHORT",loc=m15Location(m15c,M15,side);if(!loc.valid)return watch(s,type,side,"M15_LOCATION_REQUIRED",{source,canonical:{v73Prior:prior,m15Location:loc}});
  const trig=m5Trigger(m5c,M5,side),pendingRetest=!trig.valid&&trig.mss===true&&trig.displacement===true&&!trig.retest&&Number.isFinite(trig.level);
  if(!trig.valid&&!pendingRetest)return watch(s,type,side,"M5_MSS_DISPLACEMENT_RETEST_REQUIRED",{source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig}});
  const previewEntry=pendingRetest?Number(trig.level):M5.close,preview=buildTradePlan(side,previewEntry,M5,M15,H1,pendingRetest);
  if(!preview)return watch(s,type,side,"STRUCTURAL_SL_REQUIRED",{source});
  if(preview.invalid)return watch(s,type,side,preview.invalid,{source,roomR:preview.roomR});
  const planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,roomR:preview.roomR,mode:preview.mode};
  const news=await getNewsClearance(s,env);if(!news)return watch(s,type,side,"NEWS_CONTEXT_REQUIRED",{setupReady:true,planned,source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:false}}});
  if(type!=="crypto")return watch(s,type,side,"EXECUTION_QUOTE_REQUIRED",{setupReady:true,planned,source:"Twelve Data analysis",canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true}}});
  try{if(!reference)reference=await cryptoExecutionQuote(s);}catch(e){return watch(s,type,side,"FINAL_QUOTE_REQUIRED",{setupReady:true,planned,error:e?.message||String(e)});}
  if(!reference.fresh)return watch(s,type,side,"FINAL_QUOTE_STALE",{setupReady:true,planned,quote:reference});
  if(!reference.executionVerified)return watch(s,type,side,"EXECUTION_QUOTE_REQUIRED",{setupReady:true,planned,quote:reference});
  const entry=pendingRetest?Number(trig.level):reference.price,plan=buildTradePlan(side,entry,M5,M15,H1,pendingRetest);
  if(!plan||plan.invalid)return watch(s,type,side,plan?.invalid||"STRUCTURAL_SL_REQUIRED",{setupReady:true,planned,quote:reference});
  const spread=reference.ask-reference.bid,costR=spread/plan.risk;if(!Number.isFinite(costR)||costR>CONFIG.maxExecutionCostR)return watch(s,type,side,"EXECUTION_COST_TOO_HIGH",{setupReady:true,planned,costR,quote:reference});
  return {ok:true,status:plan.mode,action:plan.mode,symbol:s,market:type,side,entry:plan.entry,currentPrice:reference.price,sl:plan.sl,tp1:plan.tp1,tp2:plan.tp2,targetRR:plan.targetRR,roomR:plan.roomR,risk:{riskUsd:CONFIG.defaultRiskUsd,distance:plan.risk,quantity:CONFIG.defaultRiskUsd/plan.risk},quote:reference,source:source||reference.source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true},execution:{verified:true,spread,costR}},engine:CONFIG.version};
}
function broadRank(q){if(!q?.price)return 0;let x=0;if(q.open)x+=Math.abs((q.price-q.open)/q.open)*100;if(Number.isFinite(q.percentChange))x+=Math.abs(q.percentChange);return x;}
async function broadScan(group,env){
  const symbols=GROUPS[group],rows=[],errors=[];
  if(group==="crypto"){
    const bulk=await cryptoBulk().catch(()=>new Map());
    for(const s of symbols){const q=bulk.get(s);if(q?.price)rows.push({symbol:s,quote:q,strength:broadRank(q)});else errors.push({symbol:s,reason:"EXACT_SPOT_UNAVAILABLE"});}
    rows.sort((a,b)=>b.strength-a.strength);return {requested:symbols.length,rows,errors,h1Map:null};
  }
  let h1Map=new Map();try{h1Map=await tdBatchCandles(symbols,"1h",env,60);}catch(e){return {requested:symbols.length,rows,errors:symbols.map(symbol=>({symbol,reason:"H1_BATCH_UNAVAILABLE",error:e?.message||String(e)})),h1Map};}
  for(const s of symbols){const T=tf(h1Map.get(s)||[]);if(!T.ready){errors.push({symbol:s,reason:"H1_UNAVAILABLE"});continue;}rows.push({symbol:s,quote:{source:"Twelve Data H1",price:T.close,fresh:true},strength:Math.abs((T.close-(T.ema20??T.close))/(T.atr14||1))});}
  rows.sort((a,b)=>b.strength-a.strength);return {requested:symbols.length,rows,errors,h1Map};
}
async function prepareNonCryptoDeep(symbols,h1Map,env){
  const extra=["5min","15min","4h","1day"],maps=await Promise.all(extra.map(i=>tdBatchCandles(symbols,i,env,CONFIG.candleOutputSize))),out=new Map();
  for(const s of symbols)out.set(s,[maps[0].get(s)||[],maps[1].get(s)||[],h1Map.get(s)||[],maps[2].get(s)||[],maps[3].get(s)||[]]);
  return out;
}

function emptyGroup(){return {marketActive:[],limitActive:[],limitPending:[],watch:[]};}
function emptyBooks(){return {forex:emptyGroup(),crypto:emptyGroup(),metal:emptyGroup(),updatedAt:Date.now()};}
function normalizeBooks(v){const b=emptyBooks();if(!v||typeof v!=="object")return b;for(const g of Object.keys(GROUPS))for(const k of ["marketActive","limitActive","limitPending","watch"])if(Array.isArray(v?.[g]?.[k]))b[g][k]=v[g][k];b.updatedAt=v.updatedAt||Date.now();return b;}
async function getBooks(env){try{return normalizeBooks(await env.TRADING_STATE.get(CONFIG.keys.books,"json"));}catch{return emptyBooks();}}
async function saveBooks(env,b){b.updatedAt=Date.now();await env.TRADING_STATE.put(CONFIG.keys.books,JSON.stringify(b));}
function sideText(s){return s==="LONG"?"BUY":s==="SHORT"?"SELL":"NEUTRAL";}
function duplicate(book,s){return [...book.marketActive,...book.limitActive,...book.limitPending].some(x=>x.symbol===s);}
function toPos(sig){return {id:`${sig.symbol}-${Date.now()}`,symbol:sig.symbol,side:sig.side,entry:sig.entry,sl:sig.sl,tp:sig.targetRR===2?sig.tp2:sig.tp1,tp1:sig.tp1,tp2:sig.tp2,targetRR:sig.targetRR,origin:sig.action,status:"ACTIVE",openedAt:Date.now(),engine:sig.engine,source:sig.quote?.source};}
function fillBooks(group,books,analyses){
  const b=books[group],newItems=[];
  for(const a of analyses){
    if(group!=="crypto")continue;
    if(a.status==="MARKET"&&!duplicate(b,a.symbol)&&b.marketActive.length<CONFIG.maxMarketActive){const p=toPos(a);b.marketActive.push(p);newItems.push(p);}
    if(a.status==="LIMIT"&&!duplicate(b,a.symbol)&&b.limitPending.length<CONFIG.maxPendingLimit&&(b.limitActive.length+b.limitPending.length)<CONFIG.maxLimitActive){const p={...toPos(a),status:"PENDING",expiresAt:Date.now()+CONFIG.pendingLimitExpiryMinutes*60000};b.limitPending.push(p);newItems.push(p);}
  }
  b.watch=analyses.filter(x=>x.status==="WATCH").sort((a,b)=>Number(b.setupReady)-Number(a.setupReady)).slice(0,CONFIG.maxWatch).map(x=>({symbol:x.symbol,side:x.side,reason:x.reason,canonicalStage:x.canonicalStage,setupReady:!!x.setupReady,planned:x.planned||null,source:x.source||null,updatedAt:Date.now(),engine:CONFIG.version}));
  return newItems;
}
async function acquireLock(env){const k=CONFIG.keys.runLock;try{const old=await env.TRADING_STATE.get(k);if(old&&Date.now()-Number(old)<CONFIG.runLockTtlSec*1000)return false;await env.TRADING_STATE.put(k,String(Date.now()),{expirationTtl:CONFIG.runLockTtlSec});return true;}catch{return true;}}
async function releaseLock(env){try{await env.TRADING_STATE.delete(CONFIG.keys.runLock);}catch{}}
async function runGroup(group,env){
  if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group};
  const started=Date.now();
  try{
    const budget=await ensureTdBudget(group,env);
    if(!budget.ok){const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;}
    const broad=await broadScan(group,env),candidates=broad.rows.slice(0,CONFIG.maxCandidates),analyses=[];
    if(group==="crypto"){
      const pairs=await Promise.all(candidates.map(async c=>{try{return [c.symbol,await cryptoDeepBundle(c.symbol)];}catch(e){return [c.symbol,{error:e?.message||String(e)}];}})),map=new Map(pairs);
      for(const c of candidates){if(Date.now()-started>CONFIG.scanDeadlineMs)break;const b=map.get(c.symbol);if(!b||b.error)analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"EXCHANGE_DEEP_UNAVAILABLE",error:b?.error||"missing"});else analyses.push(await deepAnalyze(c.symbol,env,b.candles,b.quote,b.source));}
    }else{
      let prepared=new Map();try{prepared=await prepareNonCryptoDeep(candidates.map(c=>c.symbol),broad.h1Map,env);}catch{}
      for(const c of candidates){if(Date.now()-started>CONFIG.scanDeadlineMs)break;const pc=prepared.get(c.symbol);if(!pc)analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"ANALYSIS_DATA_UNAVAILABLE"});else analyses.push(await deepAnalyze(c.symbol,env,pc,null,"Twelve Data"));}
    }
    const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);
    const out={ok:true,version:CONFIG.version,group,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:candidates.length,deepOk:analyses.filter(a=>a.ok!==false).length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};
    await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;
  }finally{await releaseLock(env);}
}

async function telegram(env,method,payload){if(!env.TELEGRAM_BOT_TOKEN)throw new Error("TELEGRAM_BOT_TOKEN missing");const r=await fetchTimeout(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)}),p=await r.json();if(!p.ok)throw new Error(p.description||"Telegram error");return p;}
async function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}
function baseKeyboard(){return {inline_keyboard:[[{text:"🧭 HUB TOP SETUPS",callback_data:"hub"}],[{text:"💱 FOREX",callback_data:"scan:forex"},{text:"🪙 CRYPTO",callback_data:"scan:crypto"},{text:"🥇 METAL",callback_data:"scan:metal"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 BOOKS",callback_data:"books"}]]};}
function groupKeyboard(group,books){
  const rows=baseKeyboard().inline_keyboard,pending=(books?.[group]?.watch||[]).filter(w=>w.reason==="NEWS_CONTEXT_REQUIRED").slice(0,3);
  if(pending.length)rows.unshift(pending.map(w=>({text:`✅ Tin OK ${w.symbol}`,callback_data:`news:${group}:${w.symbol}`})));
  return {inline_keyboard:rows};
}
function hubKeyboard(books){
  const rows=baseKeyboard().inline_keyboard,p=[];
  for(const g of ["crypto","forex","metal"])for(const w of books?.[g]?.watch||[])if(w.reason==="NEWS_CONTEXT_REQUIRED"&&p.length<3)p.push({text:`✅ Tin OK ${w.symbol}`,callback_data:`news:${g}:${w.symbol}`});
  if(p.length)rows.unshift(p);return {inline_keyboard:rows};
}
function groupTitle(g){return g==="forex"?"💱 FOREX":g==="crypto"?"🪙 CRYPTO":"🥇 METAL";}
function fmtPx(v){const n=Number(v);return Number.isFinite(n)?n.toPrecision(7):"?";}
function posLine(p){return `${p.symbol} ${sideText(p.side)} | E ${fmtPx(p.entry)} | SL ${fmtPx(p.sl)} | TP ${fmtPx(p.tp)}`;}
function watchLine(w){let x=`${w.symbol} ${sideText(w.side)} | ${w.reason||"CHỜ XÁC NHẬN"}`;if(w.planned)x+=` | E~${fmtPx(w.planned.entry)} SL~${fmtPx(w.planned.sl)} TP~${fmtPx(w.planned.targetRR===2?w.planned.tp2:w.planned.tp1)}`;return x;}
function summary(group,books,run=null){
  const b=books[group],L=[groupTitle(group),"",`🟢 MARKET ${b.marketActive.length}/${CONFIG.maxMarketActive}`];
  if(b.marketActive.length)b.marketActive.forEach((p,i)=>L.push(`${i+1}. ${posLine(p)}`));else L.push("Trống");
  L.push("",`🔵 LIMIT ĐÃ KHỚP ${b.limitActive.length}/${CONFIG.maxLimitActive}`);if(b.limitActive.length)b.limitActive.forEach((p,i)=>L.push(`${i+1}. ${posLine(p)}`));else L.push("Trống");
  L.push("",`🟡 LIMIT CHỜ ${b.limitPending.length}/${CONFIG.maxPendingLimit}`);if(b.limitPending.length)b.limitPending.forEach((p,i)=>L.push(`${i+1}. ${posLine(p)}`));else L.push("Trống");
  L.push("",`👀 WATCH ${b.watch.length}/${CONFIG.maxWatch}`);if(b.watch.length)b.watch.forEach((w,i)=>L.push(`${i+1}. ${watchLine(w)}`));else L.push("Trống");
  if(run){
    if(run.status==="RATE_BUDGET_WAIT"){L.push(`⏱ Twelve Data còn ${run.diagnostics?.tdCreditsLeft??"?"} credit; cần ${run.diagnostics?.tdCreditsRequired??"?"}. Thử lại sau ~${run.retryAfterSec??60}s.`);return L.join("\n");}
    L.push(`🔍 Quét: ${run.requested} | Deep OK: ${run.deepOk}/${run.deepRequested} | Mới: ${run.newCount}`,`🧪 Coverage: ${run.broadOk}/${run.requested}`);
    const rs=run.analyses.map(a=>`${a.symbol}=${a.status}${a.reason?`(${a.reason})`:""}`).join(" | ");if(rs)L.push(`📍 ${rs}`);
  }
  return L.join("\n");
}
async function sendGroup(group,env,chatId){await sendText(env,`⏳ Đang quét ${group.toUpperCase()}...`,chatId);const run=await runGroup(group,env),books=await getBooks(env);return sendText(env,summary(group,books,run),chatId,groupKeyboard(group,books));}
function hubRank(a){if(a.status==="MARKET")return 100;if(a.status==="LIMIT")return 95;if(a.reason==="NEWS_CONTEXT_REQUIRED")return 85;if(a.reason==="EXECUTION_QUOTE_REQUIRED")return 80;if(a.reason==="FINAL_QUOTE_REQUIRED")return 75;if(a.reason==="EXECUTION_COST_TOO_HIGH")return 70;if(a.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")return 55;if(a.reason==="M15_LOCATION_REQUIRED")return 40;if(a.reason==="HTF_ALIGNMENT_REQUIRED")return 20;return 10;}
async function runHub(env){
  const runs={};for(const g of ["crypto","forex","metal"])runs[g]=await runGroup(g,env);
  const top=Object.entries(runs).flatMap(([group,r])=>(r.analyses||[]).map(a=>({...a,group}))).sort((a,b)=>hubRank(b)-hubRank(a)).slice(0,7);
  return {ok:true,version:CONFIG.version,runs,top};
}
function hubSummary(h){
  const L=[`🧭 TRADING HUB ${CONFIG.version}`,"","Top setup hiện tại:"];
  if(!h.top.length)L.push("Chưa có setup đủ tốt.");
  h.top.forEach((a,i)=>{let line=`${i+1}. ${a.symbol} ${sideText(a.side)} | ${a.status}${a.reason?` • ${a.reason}`:""}`;if(a.planned)line+=` | E~${fmtPx(a.planned.entry)} SL~${fmtPx(a.planned.sl)} TP~${fmtPx(a.planned.targetRR===2?a.planned.tp2:a.planned.tp1)}`;if(a.quote?.source||a.source)line+=` | ${a.quote?.source||a.source}`;L.push(line);});
  L.push("","MARKET/LIMIT chỉ xuất hiện khi toàn bộ canonical gate + execution quote PASS.");
  for(const g of ["forex","crypto","metal"]){const r=h.runs[g];L.push(`${groupTitle(g)}: ${r.status==="RATE_BUDGET_WAIT"?"đợi quota":`${r.broadOk}/${r.requested} coverage, deep ${r.deepOk}/${r.deepRequested}`}`);}
  return L.join("\n");
}
async function sendHub(env,chatId){await sendText(env,"⏳ HUB đang quét Crypto + Forex + Metal...",chatId);const h=await runHub(env),books=await getBooks(env);return sendText(env,hubSummary(h),chatId,hubKeyboard(books));}
function booksSummary(books){const L=["📚 BOOKS"];for(const g of ["forex","crypto","metal"]){const b=books[g];L.push(`${groupTitle(g)} • M ${b.marketActive.length} • L ${b.limitActive.length} • Pending ${b.limitPending.length} • Watch ${b.watch.length}`);}return L.join("\n");}

async function lifecycle(env){
  const books=await getBooks(env),b=books.crypto;let changed=false,pending=[];
  for(const p of b.limitPending){
    if(p.expiresAt&&Date.now()>p.expiresAt){changed=true;continue;}
    try{const q=await cryptoExecutionQuote(p.symbol),px=q.price,fill=p.side==="LONG"?px<=p.entry:px>=p.entry;if(fill&&b.limitActive.length<CONFIG.maxLimitActive){p.status="ACTIVE";p.openedAt=Date.now();b.limitActive.push(p);changed=true;await sendText(env,`🔵 LIMIT ĐÃ KHỚP\n${p.symbol} ${sideText(p.side)}\nEntry: ${p.entry}`).catch(()=>{});}else pending.push(p);}catch{pending.push(p);}
  }
  b.limitPending=pending;
  for(const key of ["marketActive","limitActive"]){const keep=[];for(const p of b[key]){try{const q=await cryptoExecutionQuote(p.symbol),px=q.price,hitTP=p.side==="LONG"?px>=p.tp:px<=p.tp,hitSL=p.side==="LONG"?px<=p.sl:px>=p.sl;if(hitTP||hitSL){changed=true;await sendText(env,`${hitTP?"✅ TAKE PROFIT":"❌ STOP LOSS"}\n${p.symbol} ${sideText(p.side)}\n${hitTP?"TP":"SL"}: ${px}`).catch(()=>{});}else keep.push(p);}catch{keep.push(p);}}b[key]=keep;}
  if(changed)await saveBooks(env,books);
}
async function setupWebhook(req,env){const u=new URL(req.url),url=`${u.origin}/telegram/webhook`,payload={url,allowed_updates:["message","callback_query"]};if(env.TELEGRAM_WEBHOOK_SECRET)payload.secret_token=env.TELEGRAM_WEBHOOK_SECRET;return telegram(env,"setWebhook",payload);}
function verifyTelegram(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}
async function handleTelegram(req,env){
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  const u=await req.json(),chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID,cb=u?.callback_query?.data,text=String(u?.message?.text||"");
  if(u?.callback_query?.id)telegram(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  if(cb==="hub"||text==="/hub")await sendHub(env,chatId);
  else if(cb?.startsWith("scan:"))await sendGroup(cb.split(":")[1],env,chatId);
  else if(cb?.startsWith("news:")){
    const [,group,symbol]=cb.split(":");if(GROUPS[group]?.includes(norm(symbol))){
      await setNewsClearance(symbol,env);await sendText(env,`✅ Tin/context OK cho ${norm(symbol)} trong ${Math.round(CONFIG.newsClearanceTtlSec/60)} phút. Đang kiểm tra lại...`,chatId);
      let a;if(group==="crypto"){try{const b=await cryptoDeepBundle(symbol);a=await deepAnalyze(symbol,env,b.candles,b.quote,b.source);}catch(e){a={ok:false,status:"DATA_BLOCK",symbol:norm(symbol),reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)};}}else a=await deepAnalyze(symbol,env);
      const books=await getBooks(env);fillBooks(group,books,[a]);await saveBooks(env,books);await sendText(env,summary(group,books,{requested:1,broadOk:1,deepRequested:1,deepOk:a.ok===false?0:1,newCount:["MARKET","LIMIT"].includes(a.status)?1:0,analyses:[a]}),chatId,groupKeyboard(group,books));
    }
  }else if(cb==="books")await sendText(env,booksSummary(await getBooks(env)),chatId,baseKeyboard());
  else if(cb==="status"||text==="/status")await sendText(env,`⚙️ SYSTEM STATUS
Version: ${CONFIG.version}
KV: ${env.TRADING_STATE?"ONLINE":"MISSING"}
Twelve Data: ${env.TWELVE_DATA_API_KEY?"CONFIGURED":"MISSING"}
Telegram: CONNECTED
Hub: UNIFIED
Crypto deep: exact exchange-native 5TF + bid/ask
Forex/Metal: Twelve Data analysis; broker execution quote required
News gate: STRICT
V73: FROZEN PRIOR
V76 R2: RESEARCH ONLY`,chatId,baseKeyboard());
  else await sendText(env,`🤖 TRADING HUB ${CONFIG.version}\nChọn HUB hoặc thị trường:`,chatId,baseKeyboard());
  return json({ok:true});
}

export default {
  async fetch(req,env){
    try{
      const u=new URL(req.url),p=u.pathname.replace(/\/$/,"")||"/";
      if(p==="/status")return json({ok:true,version:CONFIG.version,service:CONFIG.service,kv:!!env.TRADING_STATE,twelveData:!!env.TWELVE_DATA_API_KEY,telegram:!!env.TELEGRAM_BOT_TOKEN,v73:{version:V73_CONFIG.version,classification:V73_CONFIG.classification},providers:{forex:"Twelve Data batch analysis; broker execution quote required",crypto:"Exact exchange-native 5TF analysis + Bybit/OKX/Binance execution",metal:"Twelve Data batch analysis; broker execution quote required"},newsGate:{mode:"STRICT",clearanceTtlSec:CONFIG.newsClearanceTtlSec,externalUrlConfigured:!!env.NEWS_GATE_URL},hub:{enabled:true,order:["crypto","forex","metal"]}});
      if(p==="/run-now"){const g=u.searchParams.get("group");return json(await runGroup(g,env));}
      if(p==="/hub")return json(await runHub(env));
      if(p==="/telegram/setup-webhook")return json(await setupWebhook(req,env));
      if(p==="/telegram/webhook-info")return json(await telegram(env,"getWebhookInfo",{}));
      if(p==="/telegram/menu"){await sendText(env,`🤖 TRADING HUB ${CONFIG.version}\nChọn HUB hoặc thị trường:`,env.TELEGRAM_CHAT_ID,baseKeyboard());return json({ok:true});}
      if(p==="/telegram/webhook"&&req.method==="POST")return handleTelegram(req,env);
      if(p==="/books")return json(await getBooks(env));
      return json({ok:true,version:CONFIG.version,endpoints:["/status","/hub","/run-now?group=forex|crypto|metal","/telegram/setup-webhook","/telegram/webhook-info","/telegram/menu","/books"]});
    }catch(e){console.error("HTTP",e);return json({ok:false,version:CONFIG.version,error:e?.message||String(e)},500);}
  },
  async scheduled(_controller,env,ctx){ctx.waitUntil(lifecycle(env).catch(e=>console.error("CRON",e)));}
};
