import V73_CONFIG from "../data/nocut_intraday_allpass_v73.json" with { type: "json" };
import SYMBOL_KNOWLEDGE from "../data/symbol_knowledge_registry.json" with { type: "json" };

const CONFIG = {
  version: "V77.16.20",
  service: "Trading V77.16.20 Signal Integrity R7",
  tdCreditsPerMinute: 55,
  tdReserveCredits: 3,
  maxQuoteAgeSec: 65,
  cryptoQuoteAgeSec: 10,
  fetchTimeoutMs: 6500,
  scanDeadlineMs: 42000,
  candleOutputSize: 120,
  maxCandidates: 3,
  deepNonCryptoCandidates: 6,
  deepShortlist: 12,
  cryptoDeepTarget: 5,
  cryptoDeepMax: 8,
  cryptoActionTarget: 2,
  cryptoDeepCooldownMs: 220,
  autoCryptoScanMinutes: 5,
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
  actionablePlanMaxAtr: 1.15,
  unifiedTdHubBudgetMax: 50,
  runLockTtlSec: 55,
  newsClearanceTtlSec: 1800,
  keys: {
    books: "v775:books",
    history: "v775:history",
    lastRun: "v775:last_run",
    runLock: "v775:run_lock",
    newsPrefix: "v779:news_clear:",
    cryptoBroadCache: "v779:crypto_broad_cache",
    scanPrefix: "v7712:scan:",
    orderHistory: "v7712:order_history",
    shadowSetups: "v7713:shadow_setups",
    contextPrefix: "v77164:context:",
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
  "SUI","TAO","TIA","GRAM","TRUMP","UNI","WIF","WLD","AIXBT","ASTER","FARTCOIN","GRASS","IP","LIT",
  "PUMP","VIRTUAL","XPL","ZEC"
];
const CRYPTO = CRYPTO_BASE.map(x => `${x}USDT`);
const METALS = ["XAUUSD","XAGUSD"];
const INDEX_CASH = ["NAS100","US30","US500","DEX","JP225"];
const INDEX_PROVIDER = {NAS100:"NDX",US30:"DJI",US500:"SPX",DEX:"DAX",JP225:"N225"};
const MASSIVE_INDEX_PROVIDER = {NAS100:"I:NDX",US30:"I:DJI",US500:"I:SPX",DEX:"I:DAX",JP225:"I:N225"};
const INDEX_SANITY = {
  NAS100:{min:1000,max:100000}, US30:{min:5000,max:100000}, US500:{min:500,max:20000},
  DEX:{min:1000,max:100000}, JP225:{min:5000,max:100000}
};
function validIndexPrice(symbol,price){const r=INDEX_SANITY[norm(symbol)],x=Number(price);return !!r&&Number.isFinite(x)&&x>=r.min&&x<=r.max;}
function tdIndexNode(raw){return raw?.data?.values?raw.data:raw;}
function assertTdIndexIdentity(symbol,node){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,m=node?.meta||{},typ=String(m.type||"").toLowerCase(),got=norm(m.symbol||ps);if(typ&&!typ.includes("index"))throw new Error(`Twelve Data wrong instrument type ${s}: ${m.type}`);if(got&&got!==norm(ps))throw new Error(`Twelve Data wrong symbol ${s}: ${m.symbol}`);return m;}
const INDEX_PRIORS = {
  NAS100:{profile:"INDEX_GROWTH_MOMENTUM",families:["TREND","RELATIVE"],allowedModes:["TREND","RELATIVE"],riskATR:.72,newsProfile:{profileDrivers:["Fed/FOMC","US CPI/PCE/NFP","US yields","US mega-cap technology"]}},
  US30:{profile:"INDEX_BLUECHIP_ROTATION",families:["TREND","MEANREV"],allowedModes:["TREND","MEAN_REVERSION"],riskATR:.68,newsProfile:{profileDrivers:["Fed/FOMC","US macro","industrial/financial rotation"]}},
  US500:{profile:"INDEX_BROAD_RISK",families:["TREND","RELATIVE"],allowedModes:["TREND","RELATIVE"],riskATR:.66,newsProfile:{profileDrivers:["Fed/FOMC","US CPI/PCE/NFP","US yields","broad risk sentiment"]}},
  DEX:{profile:"INDEX_EUROPE_SESSION",families:["TREND","MEANREV"],allowedModes:["TREND","MEAN_REVERSION"],riskATR:.72,newsProfile:{profileDrivers:["ECB","Eurozone CPI/PMI","Germany macro"]}},
  JP225:{profile:"INDEX_ASIA_SESSION",families:["TREND","RELATIVE"],allowedModes:["TREND","RELATIVE"],riskATR:.74,newsProfile:{profileDrivers:["BoJ","Japan CPI/wages","JPY","Asia risk sentiment"]}}
};
const GROUPS = { forex: FOREX, crypto: CRYPTO, metal: METALS, index: INDEX_CASH };
const INTERVALS = ["5min","15min","1h","4h","1day"];
const memory = { tdCreditsLeft: null, cryptoBulk: null, cryptoBulkAt: 0 };

const nowSec = () => Math.floor(Date.now()/1000);
const num = v => { const n = Number(v); return Number.isFinite(n) ? n : null; };
const norm = s => String(s || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
const json = (body,status=200) => new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8"}});
function marketType(symbol){const s=norm(symbol);if(FOREX.includes(s))return "forex";if(CRYPTO.includes(s))return "crypto";if(METALS.includes(s))return "metal";if(INDEX_CASH.includes(s))return "index";return "unknown";}
function tdSymbol(symbol){const s=norm(symbol),t=marketType(s);if(t==="forex"||t==="metal")return `${s.slice(0,3)}/${s.slice(3)}`;if(t==="index")return INDEX_PROVIDER[s]||s;return s;}
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
function tdPlannedCost(group){return group==="forex"?40:group==="metal"?10:group==="index"?25:0;}
function tdRetryAfterSec(){return Math.max(3,62-(Math.floor(Date.now()/1000)%60));}
async function ensureTdBudget(group,env){
  if(group==="index"&&env.MASSIVE_API_KEY)return {ok:true,required:0,left:memory.tdCreditsLeft,primary:"MASSIVE"};
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
async function tdSingleIndexCandles(symbol,interval,env,outputsize=CONFIG.candleOutputSize){
  const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,type:"Index",interval,outputsize:String(outputsize),order:"ASC",timezone:"UTC"},env),node=tdIndexNode(p);assertTdIndexIdentity(s,node);const c=tdCandlesFromNode(node,interval);
  if(!c?.length)throw new Error(`Twelve Data index candles unavailable ${s}/${ps}`);const last=c.at(-1);if(!validIndexPrice(s,last?.close))throw new Error(`Twelve Data implausible index price ${s}: ${last?.close}`);return c;
}
async function tdBatchCandles(symbols,interval,env,outputsize=CONFIG.candleOutputSize){
  const requested=[...new Set(symbols.map(norm))],out=new Map();if(!requested.length)return out;
  if(requested.every(x=>marketType(x)==="index")){
    if(env.MASSIVE_API_KEY){const m=await massiveIndexBatchCandles(requested,interval,env,outputsize);for(const [k,v] of m)if(v?.length)out.set(k,v);}
    const missing=requested.filter(s=>!out.has(s));
    if(missing.length&&env.TWELVE_DATA_API_KEY){await Promise.all(missing.map(async s=>{try{const c=await tdSingleIndexCandles(s,interval,env,outputsize);if(c.length)out.set(s,c);}catch{}}));}
    return out;
  }
  const provider=requested.map(tdSymbol),p=await tdFetch("time_series",{symbol:provider.join(","),interval,outputsize:String(outputsize),order:"ASC",timezone:"UTC"},env);
  if(Array.isArray(p?.values)){const c=tdCandlesFromNode(p,interval);if(c)out.set(requested[0],c);return out;}
  const lookup=new Map(provider.map((x,i)=>[norm(x),requested[i]]));for(const [key,raw] of Object.entries(p||{})){const node=raw?.data?.values?raw.data:raw,c=tdCandlesFromNode(raw,interval);if(!c)continue;const canonical=lookup.get(norm(node?.meta?.symbol||key));if(canonical)out.set(canonical,c);}return out;
}
async function massiveIndexFetch(path,params,env){if(!env.MASSIVE_API_KEY)throw new Error("MASSIVE_API_KEY missing");const q=new URLSearchParams(params||{});q.set("apiKey",env.MASSIVE_API_KEY);const r=await fetchTimeout(`https://api.massive.com${path}?${q}`);const j=await r.json().catch(()=>null);if(!r.ok||!j||j.status==="ERROR")throw new Error(j?.error||j?.message||`Massive HTTP ${r.status}`);return j;}
function massiveIndexRange(interval){const now=Date.now(),d={"5min":7,"15min":14,"1h":45,"4h":180,"1day":500}[interval]||45,m={"5min":[5,"minute"],"15min":[15,"minute"],"1h":[1,"hour"],"4h":[4,"hour"],"1day":[1,"day"]}[interval]||[1,"hour"];return {from:new Date(now-d*86400000).toISOString().slice(0,10),to:new Date(now).toISOString().slice(0,10),mult:m[0],span:m[1]};}
async function massiveIndexCandles(symbol,interval,env,limit=CONFIG.candleOutputSize){const s=norm(symbol),ticker=MASSIVE_INDEX_PROVIDER[s];if(!ticker)throw new Error("Unsupported Massive index");const r=massiveIndexRange(interval),j=await massiveIndexFetch(`/v2/aggs/ticker/${encodeURIComponent(ticker)}/range/${r.mult}/${r.span}/${r.from}/${r.to}`,{adjusted:"true",sort:"asc",limit:String(Math.max(limit,120))},env),c=normalizeCandles((j.results||[]).map(x=>({timestamp:Math.floor(Number(x.t)/1000),open:x.o,high:x.h,low:x.l,close:x.c,volume:null})),candleSec(interval));if(c.length&&!validIndexPrice(s,c.at(-1)?.close))throw new Error(`Massive implausible index price ${s}: ${c.at(-1)?.close}`);return c;}
async function massiveIndexBatchCandles(symbols,interval,env,outputsize=CONFIG.candleOutputSize){const out=new Map();await Promise.all(symbols.map(async sym=>{try{const c=await massiveIndexCandles(sym,interval,env,outputsize);if(c.length)out.set(norm(sym),c);}catch{}}));return out;}
async function massiveIndexQuote(symbol,env){const s=norm(symbol),ticker=MASSIVE_INDEX_PROVIDER[s];if(!ticker)throw new Error("Unsupported Massive index");const j=await massiveIndexFetch("/v3/snapshot/indices",{ticker,limit:"10"},env),r=(j.results||[]).find(x=>x?.ticker===ticker&&!x?.error),price=num(r?.value);if(!(price>0)||!validIndexPrice(s,price))throw new Error(r?.message||r?.error||`Massive invalid index value ${s}: ${price}`);const ts=r?.last_updated?Math.floor(Number(r.last_updated)/1e9):null,age=ts?Math.max(0,nowSec()-ts):null;return {source:"Massive Indices Snapshot",requestedSymbol:s,providerSymbol:ticker,price,providerTimestamp:ts,quoteAgeSec:age,timeframe:r?.timeframe||null,marketStatus:r?.market_status||null,fresh:age==null?false:age<=900,bid:null,ask:null,executionVerified:false,analysisOnly:true};}
async function tdIndexQuote(symbol,env){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,type:"Index",interval:"1min",outputsize:"2",order:"DESC",timezone:"UTC"},env),node=tdIndexNode(p);assertTdIndexIdentity(s,node);const c=tdCandlesFromNode(node,"1min"),last=c?.at(-1),price=num(last?.close);if(!(price>0)||!validIndexPrice(s,price))throw new Error(`Twelve Data invalid native index value ${s}/${ps}: ${price}`);const age=last?.timestamp?Math.max(0,nowSec()-last.timestamp-60):null;return {source:"Twelve Data Native Index",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:age,fresh:age!==null&&age<=900,bid:null,ask:null,executionVerified:false,analysisOnly:true,assetType:node?.meta?.type||"Index"};}
async function tdQuote(symbol,env){
  if(marketType(symbol)==="index"){if(env.MASSIVE_API_KEY){try{return await massiveIndexQuote(symbol,env);}catch{}}if(env.TWELVE_DATA_API_KEY)return tdIndexQuote(symbol,env);throw new Error("No native index provider configured");}
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
function kucoinId(symbol){const x=norm(symbol);if(!x.endsWith("USDT"))throw new Error("not USDT");return x.slice(0,-4)+"-USDT";}
function gateId(symbol){const x=norm(symbol);if(!x.endsWith("USDT"))throw new Error("not USDT");return x.slice(0,-4)+"_USDT";}
function kucoinInterval(i){return {"5min":"5min","15min":"15min","1h":"1hour","4h":"4hour","1day":"1day"}[i];}
function gateInterval(i){return {"5min":"5m","15min":"15m","1h":"1h","4h":"4h","1day":"1d"}[i];}
async function kucoinCandles(symbol,interval){
  const q=new URLSearchParams({symbol:kucoinId(symbol),type:kucoinInterval(interval)}),r=await fetchTimeout("https://api.kucoin.com/api/v1/market/candles?"+q),p=await r.json().catch(()=>null);
  if(!r.ok||p?.code!=="200000"||!Array.isArray(p?.data))throw new Error("KuCoin candles unavailable");
  return normalizeCandles(p.data.map(x=>({timestamp:Number(x[0]),open:x[1],close:x[2],high:x[3],low:x[4],volume:x[5]})),candleSec(interval));
}
async function gateCandles(symbol,interval){
  const q=new URLSearchParams({currency_pair:gateId(symbol),interval:gateInterval(interval),limit:String(CONFIG.candleOutputSize)}),r=await fetchTimeout("https://api.gateio.ws/api/v4/spot/candlesticks?"+q,{headers:{Accept:"application/json"}}),p=await r.json().catch(()=>null);
  if(!r.ok||!Array.isArray(p))throw new Error("Gate candles unavailable");
  return normalizeCandles(p.filter(x=>String(x[7]??"true")!=="false").map(x=>({timestamp:Number(x[0]),open:x[5],high:x[3],low:x[4],close:x[2],volume:x[6]})),candleSec(interval));
}
async function analysisOnlyQuote(symbol,preferred){
  const s=norm(symbol);try{const m=await cryptoBulk(),q=m.get(s);if(q?.price)return {...q,analysisOnly:true,executionVerified:false,fresh:true,source:q.source||preferred||"Broad Analysis"};}catch{}return {source:preferred||"Analysis-only",price:null,bid:null,ask:null,fresh:false,executionVerified:false,analysisOnly:true};
}
async function cryptoAnalysisFallbackBundle(symbol,preferred=null){
  const s=norm(symbol),venues=preferred==="gate"?[{name:"Gate Spot Analysis",candles:gateCandles},{name:"KuCoin Spot Analysis",candles:kucoinCandles}]:[{name:"KuCoin Spot Analysis",candles:kucoinCandles},{name:"Gate Spot Analysis",candles:gateCandles}],errors=[];
  for(const v of venues){try{const candles=await Promise.all(INTERVALS.map(i=>v.candles(s,i)));if(candles.some(c=>!Array.isArray(c)||c.length<55))throw new Error("insufficient closed candles");const quote=await analysisOnlyQuote(s,v.name);return {source:v.name,quote,candles,analysisOnly:true};}catch(e){errors.push(v.name+": "+(e?.message||String(e)));}}
  throw new Error("No analysis-only deep bundle: "+errors.join(" | "));
}
async function cryptoDeepBundle(symbol,options={}){
  const s=norm(symbol),preferAnalysis=!!options.preferAnalysis,canonical=[
    {name:"Bybit Spot",quote:bybitQuote,candles:bybitCandles},
    {name:"OKX Spot",quote:okxQuote,candles:okxCandles},
    {name:"Binance Spot",quote:binanceQuote,candles:binanceCandles},
  ],errors=[];
  if(preferAnalysis){try{return await cryptoAnalysisFallbackBundle(s,options.preferredBroadSource?.includes("Gate")?"gate":null);}catch(e){errors.push(e?.message||String(e));}}
  for(const v of canonical){try{const [quote,...candles]=await Promise.all([v.quote(s),...INTERVALS.map(i=>v.candles(s,i))]);if(candles.some(c=>!Array.isArray(c)||c.length<55))throw new Error("insufficient closed candles");return {source:v.name,quote,candles,analysisOnly:false};}catch(e){errors.push(v.name+": "+(e?.message||String(e)));}}
  if(!preferAnalysis){try{return await cryptoAnalysisFallbackBundle(s);}catch(e){errors.push(e?.message||String(e));}}
  throw new Error("No exact/deep analysis bundle: "+errors.join(" | "));
}
async function cryptoExecutionQuote(symbol){
  const errors=[];for(const fn of [bybitQuote,okxQuote,binanceQuote]){try{return await fn(symbol);}catch(e){errors.push(e?.message||String(e));}}
  throw new Error(`exact venue unavailable: ${errors.join(" | ")}`);
}
async function kucoinAllTickers(){
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
function v73CryptoPriorKey(symbol){const k=norm(symbol).replace(/USDT$/,"");return k==="GRAM"?"TON":k;}
function v73Entry(symbol,type){
  let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=v73CryptoPriorKey(symbol);if(!key)return null;
  return V73_CONFIG?.[type]?.symbols?.[key]||null;
}
function v73Prior(symbol,type){
  if(type==="index"){const k=INDEX_PRIORS[norm(symbol)];if(!k)return {applicable:true,available:false,key:norm(symbol)};return {applicable:true,available:true,key:norm(symbol),source:"INDEX_CASH_PRIORS_R1",timeframe:"MULTI",status:"RUNTIME_METHOD_PRIOR",family:k.profile,families:k.families||[],profile:k.profile,entryMode:"DYNAMIC",rr:null,signalHourUTC:null,riskATR:k.riskATR,newsProfile:k.newsProfile||{profileDrivers:[]},classification:"INDEX_CASH_RUNTIME_PRIOR"};}
  const e=v73Entry(symbol,type);let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=v73CryptoPriorKey(symbol);
  if(!key)return {applicable:false,available:false};if(!e)return {applicable:true,available:false,key};
  const m=e.method||{},st=m.style||{},actions=Array.isArray(m.actions)?m.actions:[];
  const families=[...new Set([st.family,m.profile,...actions.map(a=>a.family)].filter(Boolean))];
  const riskATR=st.riskATR??actions.map(a=>a.riskATR).filter(Number.isFinite)[0]??null;
  return {applicable:true,available:true,key,source:e.source,timeframe:e.timeframe,status:m.status,family:st.family||m.profile||(m.router?"ROUTER":null),families,profile:st.profile||m.profile||e.newsProfile?.profile||null,entryMode:st.entryMode||(m.router?"ROUTER":null),rr:st.rr??null,signalHourUTC:st.signalHourUTC??m.decisionHourUTC??null,riskATR,newsProfile:e.newsProfile||null,classification:V73_CONFIG.classification};
}
function directionalVotes(D1,H4,H1){const arr=[D1,H4,H1],bull=arr.filter(x=>x.trend==="BULLISH").length,bear=arr.filter(x=>x.trend==="BEARISH").length;return {bull,bear,side:bull>=2?"LONG":bear>=2?"SHORT":"NEUTRAL"};}
function sessionFit(prior){if(!Number.isFinite(Number(prior?.signalHourUTC)))return .6;const h=new Date().getUTCHours(),d=Math.min((h-prior.signalHourUTC+24)%24,(prior.signalHourUTC-h+24)%24);return Math.max(.15,1-d/12);}
function allowedProfileModes(prior){
  const f=(prior?.families||[]).join('|').toUpperCase(),out=[];
  if(/MEANREV|REVERT|CONTRA|FADE|SLOW|SESSION/.test(f))out.push("MEAN_REVERSION");
  if(/BREADTH|RELATIVE|BTCALIGN|HYBRID|L2/.test(f))out.push("RELATIVE");
  if(/TREND|MOM|MOMENTUM|FAST|H1TREND|H4TREND|D1TREND|BTC_CORE|H1|H4|D1/.test(f))out.push("TREND");
  if(!out.length)out.push("GENERIC");return [...new Set(out)];
}
function sideFromTrendVotes(votes,H4,H1){if(votes.bull>=2)return "LONG";if(votes.bear>=2)return "SHORT";if(H4?.trend===H1?.trend&&H1?.trend!=="NEUTRAL")return H1.trend==="BULLISH"?"LONG":"SHORT";return "NEUTRAL";}
function regimeRouteScores(prior,T,context={}){
  const {M5,M15,H1,H4,D1}=T,v=directionalVotes(D1,H4,H1),allowed=allowedProfileModes(prior),baseSide=sideFromTrendVotes(v,H4,H1),r=Number(H1?.rsi14??50),m15r=Number(M15?.rsi14??50);
  const trendStrength=Math.max(v.bull,v.bear)/3,trendSide=baseSide,momOK=trendSide==="LONG"?(r>=52&&H1.close>=H1.ema20):(trendSide==="SHORT"?(r<=48&&H1.close<=H1.ema20):false),hAlign=H4?.trend===H1?.trend&&H1?.trend!=="NEUTRAL";
  const rel=Number(context.strengthNormalizedSigned??context.relativeStrength??context.strengthDiff),ctxMag=Number.isFinite(rel)?Math.min(1,Math.abs(rel)/2):0,ctxSide=Number.isFinite(rel)&&Math.abs(rel)>.05?(rel>0?"LONG":"SHORT"):"NEUTRAL";
  const hAtr=Number(H1?.atr14)||1,emaDist=Number.isFinite(H1?.ema20)?Math.abs(H1.close-H1.ema20)/hAtr:0,ext=Math.min(1,Math.max(Math.abs(r-50)/22,Math.abs(m15r-50)/24,Math.min(1,emaDist/2)));
  const longRev=H1?.bullishReclaim||M15?.bullishReclaim||M5?.bullishReclaim,shortRev=H1?.bearishReclaim||M15?.bearishReclaim||M5?.bearishReclaim;
  let mrSide="NEUTRAL";if(r<=43||m15r<=40||longRev)mrSide="LONG";if(r>=57||m15r>=60||shortRev)mrSide="SHORT";if(longRev&&!shortRev)mrSide="LONG";if(shortRev&&!longRev)mrSide="SHORT";
  const scores={};
  if(allowed.includes("TREND"))scores.TREND=Math.round(34+30*trendStrength+(momOK?15:0)+(hAlign?10:0)+6*sessionFit(prior));
  if(allowed.includes("RELATIVE")){const sideAgree=ctxSide!=="NEUTRAL"&&(trendSide===ctxSide||trendSide==="NEUTRAL");scores.RELATIVE=Math.round(34+30*ctxMag+(Number(context.score||0)>=7?10:0)+(sideAgree?12:0)+(hAlign?5:0));}
  if(allowed.includes("MEAN_REVERSION")){const revEvidence=mrSide==="LONG"?longRev:mrSide==="SHORT"?shortRev:false;scores.MEAN_REVERSION=Math.round(30+32*ext+(revEvidence?18:0)+(emaDist>=.75?8:0)+5*sessionFit(prior));}
  if(allowed.includes("GENERIC"))scores.GENERIC=Math.round(38+22*trendStrength+(hAlign?10:0)+10*ctxMag);
  const activeMode=Object.entries(scores).sort((a,b)=>b[1]-a[1])[0]?.[0]||allowed[0]||"GENERIC";
  let side=activeMode==="MEAN_REVERSION"?mrSide:activeMode==="RELATIVE"?(ctxSide!=="NEUTRAL"?ctxSide:trendSide):trendSide;
  if(activeMode==="RELATIVE"&&trendSide!=="NEUTRAL"&&ctxSide!=="NEUTRAL"&&trendSide!==ctxSide&&Math.abs(rel)<1)side=trendSide;
  let htfPass=false;
  if(activeMode==="TREND")htfPass=side!=="NEUTRAL"&&((side==="LONG"&&v.bull>=2)||(side==="SHORT"&&v.bear>=2)||hAlign);
  else if(activeMode==="RELATIVE")htfPass=side!=="NEUTRAL"&&ctxMag>=.18&&((side==="LONG"?v.bull:v.bear)>=1||Number(context.score||0)>=8);
  else if(activeMode==="MEAN_REVERSION")htfPass=side!=="NEUTRAL"&&ext>=.35&&(mrSide!=="NEUTRAL");
  else htfPass=side!=="NEUTRAL"&&(Math.max(v.bull,v.bear)>=2||hAlign);
  return {allowed,activeMode,scores,side,htfPass,votes:v,trendSide,ctxSide,ctxMag:Number(ctxMag.toFixed(3)),extension:Number(ext.toFixed(3)),emaDistATR:Number(emaDist.toFixed(3))};
}
function methodAssessment(symbol,type,T,context={}){
  const prior=v73Prior(symbol,type),route=regimeRouteScores(prior,T,context),mode=route.activeMode;let fit=Number(route.scores[mode]||50),why=["dynamic regime: "+mode];
  if(type==="forex"&&Number.isFinite(context.strengthDiff))why.push("currency-strength context");
  if(type==="crypto"){if(Number.isFinite(context.relativeStrength))why.push("BTC-relative context");if(Number.isFinite(context.fundingRate)){if(Math.abs(context.fundingRate)>.0015)fit-=6;why.push("derivatives context");}}
  if(type==="metal"&&Number.isFinite(context.relativeStrength))why.push("metal-relative context");
  if(type==="index"){if(Number.isFinite(context.relativeStrength))why.push("NQ-ES relative context");if(context.smtDivergence){why.push("H1 SMT "+context.smtSignal);if((context.smtSignal==="BULLISH"&&route.side==="LONG")||(context.smtSignal==="BEARISH"&&route.side==="SHORT"))fit+=7;else fit-=3;}}
  fit=Math.max(0,Math.min(100,Math.round(fit)));
  return {symbol:norm(symbol),type,side:route.side,methodFit:fit,activeMode:mode,allowedModes:route.allowed,routeScores:route.scores,htfPass:route.htfPass,route,profile:prior.profile||prior.family||"GENERIC",families:prior.families||[],sessionFit:Math.round(sessionFit(prior)*100),why,drivers:prior.newsProfile?.profileDrivers||prior.newsProfile?.symbolSpecific||[]};
}
function setupScore(parts={}){let x=0;x+=Math.min(25,(parts.methodFit||0)*.25);x+=parts.htf?20:Math.min(12,(parts.htfVotes||0)*4);x+=parts.location?15:0;x+=parts.trigger?15:parts.pending?8:0;x+=parts.plan?10:0;x+=Math.min(10,Math.max(0,parts.contextScore??5));x+=parts.news?3:0;x+=parts.execution?2:0;return Math.max(0,Math.min(100,Math.round(x)));}
function profileMode(intel){return intel?.activeMode||intel?.allowedModes?.[0]||"GENERIC";}
function sideTrendMatch(T,side){return side==="LONG"?T?.trend==="BULLISH":side==="SHORT"?T?.trend==="BEARISH":false;}
function adaptiveLocationPolicy(intel,M15,loc,side,context={}){
  const mode=profileMode(intel);if(loc?.valid)return {pass:true,mode:"STRUCTURAL_LOCATION",soft:false,level:loc.level};
  if(!M15?.ready||!Number.isFinite(M15.atr14)||M15.atr14<=0)return {pass:false,mode,soft:false};
  const isFx=intel?.type==="forex",strong=Number(intel?.methodFit||0)>=80&&Number(context.score||0)>=7,nearMult=isFx?(strong?1.20:1.00):(strong?1.0:.80),nearEma=Number.isFinite(M15.ema20)&&Math.abs(M15.close-M15.ema20)<=M15.atr14*nearMult;
  const continuation=side==="LONG"?(M15.bullishBreak||M15.bullishReclaim||sideTrendMatch(M15,side)):(M15.bearishBreak||M15.bearishReclaim||sideTrendMatch(M15,side));
  if(isFx&&["TREND","RELATIVE"].includes(mode)&&Number(intel.methodFit||0)>=46&&Number(context.score||0)>=5.2&&nearEma&&continuation)return {pass:true,mode:"FX_SESSION_CONTINUATION_ZONE",soft:true,level:M15.ema20};
  if(mode==="MEAN_REVERSION")return {pass:false,mode,soft:false};
  if(mode==="TREND"&&intel.methodFit>=48&&nearEma&&continuation)return {pass:true,mode:"TREND_CONTINUATION_ZONE",soft:true,level:M15.ema20};
  if(mode==="RELATIVE"&&intel.methodFit>=48&&Number(context.score||0)>=6&&nearEma&&continuation)return {pass:true,mode:"RELATIVE_CONTINUATION_ZONE",soft:true,level:M15.ema20};
  if(mode==="GENERIC"&&intel.methodFit>=60&&nearEma&&(M15.bullishBreak||M15.bearishBreak||M15.bullishReclaim||M15.bearishReclaim||sideTrendMatch(M15,side)))return {pass:true,mode:"QUALITY_CONTINUATION_ZONE",soft:true,level:M15.ema20};
  return {pass:false,mode,soft:false,level:Number.isFinite(M15.ema20)?M15.ema20:null};
}
function adaptiveTriggerPolicy(intel,M5,trig,side,context={}){
  const pending=!trig?.valid&&trig?.mss===true&&trig?.displacement===true&&!trig?.retest&&Number.isFinite(trig?.level);
  if(trig?.valid)return {pass:true,pending:false,mode:"MSS_DISPLACEMENT_RETEST",level:trig.level};
  if(pending)return {pass:true,pending:true,mode:"MSS_DISPLACEMENT_LIMIT",level:trig.level};
  const mode=profileMode(intel),r=Number(M5?.rsi14??50),trend=sideTrendMatch(M5,side);
  const impulse=side==="LONG"?trend&&r>=50&&r<=78&&M5.close>=M5.ema20:trend&&r<=50&&r>=22&&M5.close<=M5.ema20;
  const structuralImpulse=side==="LONG"?(M5.bullishBreak||M5.bullishReclaim):(M5.bearishBreak||M5.bearishReclaim),isFx=intel?.type==="forex";
  const fxImpulse=side==="LONG"?trend&&r>=48&&r<=74&&M5.close>=M5.ema20:trend&&r<=52&&r>=26&&M5.close<=M5.ema20;
  if(isFx&&["TREND","RELATIVE"].includes(mode)&&Number(intel.methodFit||0)>=47&&Number(context.score||0)>=5.2&&fxImpulse&&(structuralImpulse||Math.abs(r-50)>=3||Number(intel.methodFit||0)>=72))return {pass:true,pending:false,mode:"FX_M5_SESSION_CONTINUATION",level:M5.close,soft:true};
  if(mode==="MEAN_REVERSION")return {pass:false,pending:false,mode};
  if(mode==="TREND"&&intel.methodFit>=50&&impulse&&(structuralImpulse||Math.abs(r-50)>=4||intel.methodFit>=76))return {pass:true,pending:false,mode:"M5_MOMENTUM_CONTINUATION",level:M5.close,soft:true};
  if(mode==="RELATIVE"&&intel.methodFit>=50&&Number(context.score||0)>=6&&impulse&&(structuralImpulse||intel.methodFit>=76))return {pass:true,pending:false,mode:"M5_RELATIVE_BREAK",level:M5.close,soft:true};
  if(mode==="GENERIC"&&intel.methodFit>=62&&impulse&&(structuralImpulse||intel.methodFit>=78))return {pass:true,pending:false,mode:"M5_QUALITY_BREAK",level:M5.close,soft:true};
  return {pass:false,pending:false,mode,level:trig?.level??null};
}
function indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior,intel=null){
  if(!M5?.ready||!M15?.ready||!["LONG","SHORT"].includes(side))return null;let e=Number(locPolicy?.level);if(!Number.isFinite(e))e=Number(M15.ema20);
  const atr=Number(M15.atr14);if(!Number.isFinite(e)||!Number.isFinite(atr)||atr<=0)return null;const dist=Math.abs(e-M15.close)/atr,correct=side==="LONG"?e<M15.close:e>M15.close;if(!correct||dist<.05||dist>.90)return null;
  const p=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!p||p.invalid)return null;const g=limitGeometry(side,M15.close,e,M5,M15,p),q=rrQuality(p,intel);if(!g.pass||!q.pass)return null;
  return {entry:p.entry,sl:p.sl,tp1:p.tp1,tp2:p.tp2,targetRR:p.targetRR,tp1RR:p.tp1RR,tp2RR:p.tp2RR,roomR:p.roomR,mode:"INDICATIVE_LIMIT",targetSource:p.targetSource,indicative:true,currentPrice:M15.close,geometry:g,entryStyle:"STRUCTURAL_PULLBACK_ZONE",minQualityRR:q.minRR,rrQualityPass:true};
}
function conditionalPlanFromRoute(intel,M5,M15,H1,H4,D1,prior){
  if(!M5?.ready||!M15?.ready)return null;const route=intel?.route||{},side=["LONG","SHORT"].includes(intel?.side)?intel.side:(["LONG","SHORT"].includes(route.trendSide)?route.trendSide:(["LONG","SHORT"].includes(route.ctxSide)?route.ctxSide:"NEUTRAL"));
  if(side==="NEUTRAL"||Number(intel?.methodFit||0)<52)return null;const e=Number(M15.ema20);if(!Number.isFinite(e)||!Number.isFinite(M15.atr14)||M15.atr14<=0)return null;
  const dist=Math.abs(e-M15.close)/M15.atr14,correct=side==="LONG"?e<M15.close:e>M15.close;if(!correct||dist<.08||dist>.85)return null;
  const p=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!p||p.invalid)return null;const q=rrQuality(p,intel),g=limitGeometry(side,M15.close,e,M5,M15,p);if(!q.pass||!g.pass)return null;
  return {side,entry:p.entry,sl:p.sl,tp1:p.tp1,tp2:p.tp2,targetRR:p.targetRR,tp1RR:p.tp1RR,tp2RR:p.tp2RR,roomR:p.roomR,mode:"INDICATIVE_LIMIT",targetSource:p.targetSource,indicative:true,conditional:true,currentPrice:M15.close,entryStyle:"CONDITIONAL_HTF_PULLBACK",minQualityRR:q.minRR,rrQualityPass:true,geometry:g};
}
function actionableRank(a){let x=Number(a?.score)||0;if(a?.status==="MARKET")x+=1000;else if(a?.status==="LIMIT")x+=900;else if(a?.status==="MARKET_SIGNAL")x+=800;else if(a?.status==="MARKET_PLAN")x+=700;else if(a?.status==="LIMIT_PLAN")x+=650;else if(a?.planned?.mode==="MARKET")x+=500;else if(a?.planned?.mode==="LIMIT"||a?.planned?.mode==="INDICATIVE_LIMIT")x+=420;else if(a?.setupReady)x+=150;const p=a?.planned||a,rr=Number(p?.targetRR),g=p?.geometry||p?.marketGeometry||{};if(Number.isFinite(rr))x+=Math.min(80,rr*22);if(Number.isFinite(g.distanceATR))x+=Math.max(0,24-Math.abs(g.distanceATR-.30)*30);if(Number.isFinite(p?.confluence))x+=Math.min(20,Number(p.confluence)*5);if(a?.contextOnly)x-=600;return x;}

function watch(symbol,type,side,reason,extra={}){return {ok:true,status:"WATCH",action:"WATCH",symbol,market:type,side,reason,canonicalStage:reason,engine:CONFIG.version,...extra};}
async function getNewsClearance(symbol,env){
  const s=norm(symbol),key=CONFIG.keys.newsPrefix+s;
  try{const raw=await env.TRADING_STATE?.get(key,"json");if(raw?.clearedAt&&Date.now()-Number(raw.clearedAt)<=CONFIG.newsClearanceTtlSec*1000)return raw;}catch{}
  if(env.NEWS_GATE_URL){try{const u=new URL(env.NEWS_GATE_URL);u.searchParams.set("symbol",s);u.searchParams.set("market",marketType(s));const r=await fetchTimeout(u.toString());const p=await r.json();if(r.ok&&p?.clear===true){const v={clearedAt:Date.now(),source:"NEWS_GATE_URL",detail:p.detail||null,soft:false};await env.TRADING_STATE?.put(key,JSON.stringify(v),{expirationTtl:CONFIG.newsClearanceTtlSec});return v;}return null;}catch{return null;}}
  return {clearedAt:Date.now(),source:"SOFT_NO_EXTERNAL_NEWS_FEED",soft:true,detail:"No live news gate configured; technical plan may proceed but Hub labels news as unverified."};
}
async function setNewsClearance(symbol,env){const s=norm(symbol),v={clearedAt:Date.now(),source:"TELEGRAM_MANUAL"};await env.TRADING_STATE?.put(`${CONFIG.keys.newsPrefix}${s}`,JSON.stringify(v),{expirationTtl:CONFIG.newsClearanceTtlSec});return v;}
function structuralCandidates(side,entry,M5,M15,H1,H4,D1){
  const raw=side==="LONG"?[M5.liquidityLow20,M15.liquidityLow20,H1.liquidityLow20,H4.liquidityLow20,D1.liquidityLow20]:[M5.liquidityHigh20,M15.liquidityHigh20,H1.liquidityHigh20,H4.liquidityHigh20,D1.liquidityHigh20];
  return raw.filter(Number.isFinite).filter(v=>side==="LONG"?v<entry:v>entry).sort((a,b)=>Math.abs(a-entry)-Math.abs(b-entry));
}
function targetCandidates(side,entry,M15,H1,H4,D1){
  const raw=side==="LONG"?[M15.liquidityHigh20,H1.liquidityHigh20,H4.liquidityHigh20,D1.liquidityHigh20]:[M15.liquidityLow20,H1.liquidityLow20,H4.liquidityLow20,D1.liquidityLow20];
  return [...new Set(raw.filter(Number.isFinite).filter(v=>side==="LONG"?v>entry:v<entry))].sort((a,b)=>Math.abs(a-entry)-Math.abs(b-entry));
}
function buildTradePlan(side,entry,M5,M15,H1,H4,D1,pendingRetest,prior={}){
  if(!Number.isFinite(M5.atr14)||M5.atr14<=0)return null;const atrFloor=Math.max(M5.atr14*.55,(Number(prior.riskATR)||.55)*M5.atr14*.7),structures=structuralCandidates(side,entry,M5,M15,H1,H4,D1),anchor=structures[0]??(side==="LONG"?entry-atrFloor:entry+atrFloor),buffer=M5.atr14*.12;
  const sl=side==="LONG"?Math.min(anchor-buffer,entry-atrFloor):Math.max(anchor+buffer,entry+atrFloor),risk=Math.abs(entry-sl);if(!Number.isFinite(risk)||risk<=0)return null;
  const valid=targetCandidates(side,entry,M15,H1,H4,D1).map(v=>({price:v,rr:Math.abs(v-entry)/risk})).filter(x=>x.rr>=.80&&x.rr<=4);if(!valid.length)return {invalid:"CLEAN_TARGET_REQUIRED",risk,roomR:0};
  const tp1=valid[0],tp2=valid.find(x=>x.rr>=Math.max(1.4,tp1.rr+.35)&&x.rr<=3.2)||null,best=tp2||tp1;return {entry,sl,risk,roomR:best.rr,targetRR:Number(best.rr.toFixed(2)),tp1:tp1.price,tp1RR:Number(tp1.rr.toFixed(2)),tp2:(tp2||tp1).price,tp2RR:Number((tp2||tp1).rr.toFixed(2)),mode:pendingRetest?"LIMIT":"MARKET",targetSource:"STRUCTURE_LIQUIDITY",targetTier:tp2?"PRIMARY_PLUS_EXTENSION":"PRIMARY_ONLY"};
}
function symbolKnowledge(symbol){const s=canonicalUserSymbol(symbol),k=s.endsWith("USDT")?s.slice(0,-4):s;return INDEX_PRIORS[s]||SYMBOL_KNOWLEDGE?.symbols?.[s]||SYMBOL_KNOWLEDGE?.symbols?.[k]||null;}
function minimumQualityRR(intel){const mode=profileMode(intel),type=intel?.type||"unknown";let x=mode==="MEAN_REVERSION"?1.10:mode==="TREND"?1.30:mode==="RELATIVE"?1.25:1.30;if(type==="index")x=Math.max(x,mode==="MEAN_REVERSION"?1.20:1.35);else if(type==="metal")x=Math.max(x,mode==="MEAN_REVERSION"?1.18:1.28);else if(type==="crypto")x=Math.max(x,mode==="MEAN_REVERSION"?1.15:1.35);else if(type==="forex")x=Math.max(x,mode==="MEAN_REVERSION"?1.10:1.20);if(Number(intel?.methodFit)>=90)x-=.05;return Math.max(1.1,Number(x.toFixed(2)));}
function rrQuality(plan,intel){const min=minimumQualityRR(intel),rr=Number(plan?.targetRR);return {pass:Number.isFinite(rr)&&rr>=min,minRR:min,targetRR:rr};}
function limitGeometry(side,current,entry,M5,M15,plan){const atr=Number(M15?.atr14)||Number(M5?.atr14)||0;if(!atr||!Number.isFinite(current)||!Number.isFinite(entry))return {pass:false,reason:"NO_ATR"};const dist=Math.abs(current-entry)/atr,correct=side==="LONG"?entry<current:entry>current,notInvalid=side==="LONG"?entry>Number(plan?.sl):entry<Number(plan?.sl);return {pass:correct&&notInvalid&&dist>=.05&&dist<=1.05,distanceATR:Number(dist.toFixed(2)),correctSide:correct,notInvalid};}
function marketGeometry(side,current,M5,trigPolicy){const atr=Number(M5?.atr14)||0,ref=Number(trigPolicy?.level);if(!atr||!Number.isFinite(current))return {pass:false,chaseATR:null};const chase=Number.isFinite(ref)?Math.abs(current-ref)/atr:0,r=Number(M5?.rsi14??50),notExtreme=side==="LONG"?r<=80:r>=20;return {pass:chase<=.70&&notExtreme,chaseATR:Number(chase.toFixed(2)),rsi:r,notExtreme};}
function plannedModeLabel(p){return p?.mode==="MARKET"?"MARKET_PLAN":(p?.mode==="LIMIT"||p?.mode==="INDICATIVE_LIMIT")?"LIMIT_PLAN":"WATCH";}
function planSignal(symbol,type,side,reason,planned,extra={}){const intel=extra?.method||null,q=rrQuality(planned,intel);if(planned&&Number.isFinite(Number(planned.targetRR))&&!q.pass)return watch(symbol,type,side,"RR_QUALITY_REQUIRED",{...extra,rejectedPlan:{entry:planned.entry,sl:planned.sl,tp1:planned.tp1,tp2:planned.tp2,targetRR:planned.targetRR,minQualityRR:q.minRR,entryStyle:planned.entryStyle||null},planned:null});const status=plannedModeLabel(planned);return {ok:true,status,action:status,symbol,market:type,side,reason,canonicalStage:reason,planned:{...planned,minQualityRR:planned?.minQualityRR??q.minRR,rrQualityPass:true,planType:status,executionVerified:false},executionReady:false,engine:CONFIG.version,...extra};}
function refinedLimitPlan(side,current,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy){
  if(!Number.isFinite(current)||!Number.isFinite(M15?.atr14)||M15.atr14<=0)return null;const atr=M15.atr14,raw=[trigPolicy?.level,locPolicy?.level,M15.ema20,M5.ema20,side==="LONG"?M15.liquidityLow20:M15.liquidityHigh20].filter(Number.isFinite),cand=[...new Set(raw)].filter(e=>side==="LONG"?e<current:e>current).filter(e=>Math.abs(current-e)/atr<=CONFIG.actionablePlanMaxAtr);let best=null;
  for(const e of cand){const p=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!p||p.invalid)continue;const q=rrQuality(p,intel),g=limitGeometry(side,current,e,M5,M15,p);if(!q.pass||!g.pass)continue;const conf=raw.filter(x=>Math.abs(x-e)<=atr*.12).length,score=conf*25+Math.min(40,p.targetRR*12)-Math.abs(g.distanceATR-.30)*12;if(!best||score>best._score)best={...p,mode:"LIMIT",indicative:true,currentPrice:current,entryStyle:"STRUCTURE_RETEST_LIMIT",minQualityRR:q.minRR,rrQualityPass:true,geometry:g,confluence:conf,_score:score};}
  if(best)delete best._score;return best;
}
function planOrWatch(symbol,type,side,reason,planned,extra={}){if(planned){const q=rrQuality(planned,extra.method||extra?.base?.method||{});if(planned.rrQualityPass===true||q.pass)return planSignal(symbol,type,side,reason,{...planned,minQualityRR:planned.minQualityRR??q.minRR,rrQualityPass:true},extra);}return watch(symbol,type,side,reason,{...extra,planned:planned||null});}
function routeRescueSide(intel){const r=intel?.route||{};for(const x of [intel?.side,r.trendSide,r.ctxSide])if(["LONG","SHORT"].includes(x))return x;return "NEUTRAL";}
function structuralFallbackLimit(side,current,M5,M15,H1,H4,D1,prior,intel){
  if(!["LONG","SHORT"].includes(side)||!M5?.ready||!M15?.ready||!Number.isFinite(current)||!Number.isFinite(M15.atr14)||M15.atr14<=0)return null;
  if(Number(intel?.methodFit||0)<42)return null;const atr=Number(M15.atr14),mid=(Number.isFinite(M15.liquidityHigh20)&&Number.isFinite(M15.liquidityLow20))?(M15.liquidityHigh20+M15.liquidityLow20)/2:null;
  const raw=[M5.ema20,M15.ema20,H1?.ema20,mid,side==="LONG"?M5.liquidityLow20:M5.liquidityHigh20,side==="LONG"?M15.liquidityLow20:M15.liquidityHigh20,side==="LONG"?H1?.liquidityLow20:H1?.liquidityHigh20].filter(Number.isFinite);
  const cand=[...new Set(raw)].filter(e=>side==="LONG"?e<current:e>current).filter(e=>{const d=Math.abs(current-e)/atr;return d>=.05&&d<=.90;});let best=null;
  for(const e of cand){const plan=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!plan||plan.invalid)continue;const q=rrQuality(plan,intel),g=limitGeometry(side,current,e,M5,M15,plan);if(!q.pass||!g.pass)continue;const conf=raw.filter(x=>Math.abs(x-e)<=atr*.12).length,rr=Number(plan.targetRR)||0,score=conf*28+Math.min(45,rr*13)-Math.abs(g.distanceATR-.35)*10;if(!best||score>best._score)best={...plan,mode:"LIMIT",indicative:true,conditional:true,currentPrice:current,entryStyle:"STRUCTURAL_FALLBACK_LIMIT",minQualityRR:q.minRR,rrQualityPass:true,geometry:g,confluence:conf,_score:score};}
  if(best)delete best._score;return best;
}
function rescuePlan(side,current,M5,M15,H1,H4,D1,prior,intel,locPolicy={},trigPolicy={}){return refinedLimitPlan(side,current,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy)||structuralFallbackLimit(side,current,M5,M15,H1,H4,D1,prior,intel);}



async function deepAnalyze(symbol,env,candles=null,reference=null,source=null,context={}){
  const s=canonicalUserSymbol(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};const prior=v73Prior(s,type),knowledge=symbolKnowledge(s);
  try{if(!candles){if(type==="crypto"){const b=await cryptoDeepBundle(s);candles=b.candles;reference=b.quote;source=b.source;}else candles=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env).then(m=>m.get(s)||[])));}}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"ANALYSIS_DATA_UNAVAILABLE",error:e?.message||String(e)};}
  const [m5c,m15c]=candles||[],[M5,M15,H1,H4,D1]=(candles||[]).map(tf);if(!M5||[M5,M15,H1,H4,D1].some(x=>!x?.ready))return watch(s,type,"NEUTRAL","TIMEFRAME_DATA_REQUIRED",{source,score:5,canonical:{v73Prior:prior}});
  const intel=methodAssessment(s,type,{M5,M15,H1,H4,D1},context),votes=intel.route?.votes||directionalVotes(D1,H4,H1),side=intel.side,htf=!!intel.htfPass;
  const base={source,method:intel,knowledge:knowledge?{canonicalSymbol:knowledge.canonicalSymbol,allowedModes:knowledge.allowedModes,riskATR:knowledge.riskATR,newsProfile:knowledge.newsProfile,calibration:knowledge.calibration}:null,context,canonical:{v73Prior:prior},score:setupScore({methodFit:intel.methodFit,htf,htfVotes:Math.max(votes.bull,votes.bear),contextScore:context.score??5})};
  if(side==="NEUTRAL"||!htf){const rs=routeRescueSide(intel),cp=conditionalPlanFromRoute(intel,M5,M15,H1,H4,D1,prior)||rescuePlan(rs,M15.close,M5,M15,H1,H4,D1,prior,intel,{},{});if(cp)return planSignal(s,type,cp.side||rs,"HTF_METHOD_ALIGNMENT_REQUIRED",cp,{...base,score:Math.max(base.score,40),entryPolicy:{profile:profileMode(intel),conditional:true,rescue:true}});return watch(s,type,side,"HTF_METHOD_ALIGNMENT_REQUIRED",base);}
  const loc=m15Location(m15c,M15,side),locPolicy=adaptiveLocationPolicy(intel,M15,loc,side,context);base.score=setupScore({methodFit:intel.methodFit,htf:true,location:locPolicy.pass,contextScore:context.score??5});
  if(!locPolicy.pass){const planned=indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior,intel)||rescuePlan(side,M15.close,M5,M15,H1,H4,D1,prior,intel,locPolicy,{})||conditionalPlanFromRoute(intel,M5,M15,H1,H4,D1,prior);if(planned)return planSignal(s,type,planned.side||side,"M15_LOCATION_REQUIRED",planned,{...base,score:Math.max(base.score,44),entryPolicy:{profile:profileMode(intel),location:locPolicy},canonical:{...base.canonical,m15Location:loc}});return watch(s,type,side,"M15_LOCATION_REQUIRED",{...base,entryPolicy:{profile:profileMode(intel),location:locPolicy},canonical:{...base.canonical,m15Location:loc}});}
  const trig=m5Trigger(m5c,M5,side),trigPolicy=adaptiveTriggerPolicy(intel,M5,trig,side,context),pendingRetest=!!trigPolicy.pending;base.score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:trigPolicy.pass&&!pendingRetest,pending:pendingRetest,contextScore:context.score??5});
  if(!trigPolicy.pass){const planned=indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior,intel)||rescuePlan(side,M5.close,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy)||conditionalPlanFromRoute(intel,M5,M15,H1,H4,D1,prior);if(planned)return planSignal(s,type,planned.side||side,"M5_MSS_DISPLACEMENT_RETEST_REQUIRED",planned,{...base,score:Math.max(base.score,48),entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig}});return watch(s,type,side,"M5_MSS_DISPLACEMENT_RETEST_REQUIRED",{...base,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig}});}
  const previewEntry=pendingRetest?Number(trigPolicy.level):M5.close,preview=buildTradePlan(side,previewEntry,M5,M15,H1,H4,D1,pendingRetest,prior);if(!preview)return watch(s,type,side,"STRUCTURAL_SL_REQUIRED",base);if(preview.invalid){const alt=rescuePlan(side,M5.close,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,preview.invalid,alt,{...base,score:Math.max(base.score,50),setupReady:true});return watch(s,type,side,preview.invalid,{...base,roomR:preview.roomR});}
  const quality=rrQuality(preview,intel),planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,tp1RR:preview.tp1RR,tp2RR:preview.tp2RR,roomR:preview.roomR,mode:preview.mode,currentPrice:M5.close,targetSource:preview.targetSource,targetTier:preview.targetTier,entryStyle:trigPolicy.mode,adaptive:!!(locPolicy.soft||trigPolicy.soft),minQualityRR:quality.minRR,rrQualityPass:quality.pass};
  let score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:!pendingRetest,pending:pendingRetest,plan:true,contextScore:context.score??5});
  if(!quality.pass){const alt=rescuePlan(side,M5.close,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,"RR_QUALITY_REQUIRED",alt,{...base,score:Math.max(score,52),setupReady:true,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,rrQuality:quality,limitGeometry:alt.geometry}});return watch(s,type,side,"RR_QUALITY_REQUIRED",{...base,score,setupReady:true,planned,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,rrQuality:quality}});}
  const news=await getNewsClearance(s,env);if(!news)return planSignal(s,type,side,"NEWS_CONTEXT_REQUIRED",planned,{...base,score,setupReady:true,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:false}}});
  const newsSoft=!!news.soft;score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:!pendingRetest,pending:pendingRetest,plan:true,contextScore:context.score??5,news:!newsSoft});
  if(pendingRetest){const lg=limitGeometry(side,M5.close,preview.entry,M5,M15,preview);if(!lg.pass){const alt=rescuePlan(side,M5.close,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,"LIMIT_GEOMETRY_REQUIRED",alt,{...base,score,setupReady:true,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,limitGeometry:alt.geometry}});return watch(s,type,side,"LIMIT_GEOMETRY_REQUIRED",{...base,score,setupReady:true,planned:{...planned,geometry:lg},entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,limitGeometry:lg}});}}
  if(type!=="crypto"){let signalQuote=reference;try{if(!signalQuote?.price||signalQuote.fresh===false)signalQuote=await tdQuote(s,env);}catch{}const livePrice=Number(signalQuote?.price),hasFresh=Number.isFinite(livePrice)&&livePrice>0&&signalQuote?.fresh!==false;let p=planned,mg=null,liveQuality=quality;if(!pendingRetest&&hasFresh){mg=marketGeometry(side,livePrice,M5,trigPolicy);const rebuilt=buildTradePlan(side,livePrice,M5,M15,H1,H4,D1,false,prior);if(rebuilt&&!rebuilt.invalid){const q2=rrQuality(rebuilt,intel);if(q2.pass){p={...rebuilt,marketGeometry:mg,minQualityRR:q2.minRR,rrQualityPass:true};liveQuality=q2;}}if(!mg.pass){const alt=rescuePlan(side,livePrice,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)p=alt;else return watch(s,type,side,"MARKET_GEOMETRY_REQUIRED",{...base,score,setupReady:true,analysisQuote:signalQuote,planned:{...planned,marketGeometry:mg},entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},source:signalQuote?.source||source,canonical:{...base.canonical,marketGeometry:mg}});}}
    const advisoryFit=type==="forex"?48:type==="metal"?52:type==="index"?52:999,advisoryContext=type==="forex"?5.2:type==="metal"?5.5:5.4;
    const marketAdvisory=["forex","metal","index"].includes(type)&&!pendingRetest&&hasFresh&&mg?.pass&&Number(intel.methodFit||0)>=advisoryFit&&Number(context.score||0)>=advisoryContext&&liveQuality.pass;
    if(marketAdvisory)return {ok:true,status:"MARKET_SIGNAL",action:"MARKET_SIGNAL",symbol:s,market:type,side,score:Math.max(score,55),method:intel,context,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},entry:livePrice,currentPrice:livePrice,sl:p.sl,tp1:p.tp1,tp2:p.tp2,targetRR:p.targetRR,tp1RR:p.tp1RR,tp2RR:p.tp2RR,roomR:p.roomR,analysisQuote:signalQuote,planned:{...p,mode:"MARKET",signalOnly:true,analysisQuote:true},executionReady:false,executionAuthority:"SIGNAL_ONLY",quote:{...signalQuote,analysisOnly:true,executionVerified:false},source:signalQuote?.source||source||"analysis quote",canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:true,soft:newsSoft,source:news.source},marketGeometry:mg},engine:CONFIG.version};
    return planSignal(s,type,side,hasFresh?"EXECUTION_QUOTE_REQUIRED":"FINAL_QUOTE_REQUIRED",p,{...base,score,setupReady:true,analysisQuote:signalQuote||null,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},source:signalQuote?.source||source,canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:true,soft:newsSoft,source:news.source}}});}
  try{if(!reference||reference.analysisOnly)reference=await cryptoExecutionQuote(s);}catch(e){return planSignal(s,type,side,"FINAL_QUOTE_REQUIRED",planned,{...base,score,setupReady:true,error:e?.message||String(e)});}if(!reference.fresh)return planSignal(s,type,side,"FINAL_QUOTE_STALE",planned,{...base,score,setupReady:true,quote:reference});if(!reference.executionVerified)return planSignal(s,type,side,"EXECUTION_QUOTE_REQUIRED",planned,{...base,score,setupReady:true,quote:reference});
  if(!pendingRetest){const mg=marketGeometry(side,reference.price,M5,trigPolicy);if(!mg.pass){const alt=rescuePlan(side,reference.price,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,"MARKET_GEOMETRY_REQUIRED",alt,{...base,score,setupReady:true,quote:reference,canonical:{...base.canonical,marketGeometry:mg,limitGeometry:alt.geometry}});return watch(s,type,side,"MARKET_GEOMETRY_REQUIRED",{...base,score,setupReady:true,planned:{...planned,marketGeometry:mg},quote:reference,canonical:{...base.canonical,marketGeometry:mg}});}}
  const entry=pendingRetest?Number(trigPolicy.level):reference.price,plan=buildTradePlan(side,entry,M5,M15,H1,H4,D1,pendingRetest,prior);if(!plan||plan.invalid){const alt=rescuePlan(side,reference.price,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,plan?.invalid||"STRUCTURAL_SL_REQUIRED",alt,{...base,score,setupReady:true,quote:reference});return watch(s,type,side,plan?.invalid||"STRUCTURAL_SL_REQUIRED",{...base,score,setupReady:true,planned,quote:reference});}
  if(pendingRetest){const lg=limitGeometry(side,reference.price,entry,M5,M15,plan);if(!lg.pass){const alt=rescuePlan(side,reference.price,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,"LIMIT_GEOMETRY_REQUIRED",alt,{...base,score,setupReady:true,quote:reference,canonical:{...base.canonical,limitGeometry:alt.geometry}});return watch(s,type,side,"LIMIT_GEOMETRY_REQUIRED",{...base,score,setupReady:true,planned:{...planned,geometry:lg},quote:reference,canonical:{...base.canonical,limitGeometry:lg}});}}
  const spread=reference.ask-reference.bid,costR=spread/plan.risk;if(!Number.isFinite(costR)||costR>CONFIG.maxExecutionCostR){const alt=rescuePlan(side,reference.price,M5,M15,H1,H4,D1,prior,intel,locPolicy,trigPolicy);if(alt)return planSignal(s,type,side,"EXECUTION_COST_TOO_HIGH",alt,{...base,score,setupReady:true,costR,quote:reference});return watch(s,type,side,"EXECUTION_COST_TOO_HIGH",{...base,score,setupReady:true,planned,costR,quote:reference});}
  score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:true,plan:true,contextScore:context.score??5,news:true,execution:true});
  return {ok:true,status:plan.mode,action:plan.mode,symbol:s,market:type,side,score,method:intel,context,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},entry:plan.entry,currentPrice:reference.price,sl:plan.sl,tp1:plan.tp1,tp2:plan.tp2,targetRR:plan.targetRR,tp1RR:plan.tp1RR,tp2RR:plan.tp2RR,roomR:plan.roomR,risk:{riskUsd:CONFIG.defaultRiskUsd,distance:plan.risk,quantity:CONFIG.defaultRiskUsd/plan.risk},quote:reference,source:source||reference.source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true},execution:{verified:true,spread,costR}},engine:CONFIG.version};
}
async function quotePool(symbols,fn,concurrency=6){
  const out=new Map(),list=[...symbols],state={i:0};
  async function worker(){while(state.i<list.length){const idx=state.i++,sym=list[idx];try{const q=await fn(sym);if(q?.price&&q.fresh!==false)out.set(sym,q);}catch{}await new Promise(r=>setTimeout(r,35));}}
  await Promise.all(Array.from({length:Math.min(concurrency,list.length||1)},()=>worker()));return out;
}
async function loadCryptoBroadCache(env,maxAgeMs=120000){
  const out=new Map();try{const p=await env.TRADING_STATE?.get(CONFIG.keys.cryptoBroadCache,"json");for(const row of p?.rows||[]){if(!row?.symbol||!row?.quote||!Number.isFinite(Number(row.cachedAt)))continue;if(Date.now()-Number(row.cachedAt)>maxAgeMs)continue;out.set(norm(row.symbol),{...row.quote,broadCached:true,broadCachedAt:Number(row.cachedAt)});}}catch{}return out;
}
async function saveCryptoBroadCache(env,map){
  try{const rows=[];for(const [symbol,quote] of map){if(!CRYPTO.includes(norm(symbol))||!quote?.price)continue;rows.push({symbol:norm(symbol),quote,cachedAt:Number(quote.broadCachedAt)||Date.now()});}await env.TRADING_STATE?.put(CONFIG.keys.cryptoBroadCache,JSON.stringify({savedAt:Date.now(),rows}),{expirationTtl:300});}catch{}
}
async function cryptoBroadMap(symbols,env){
  let map=await cryptoBulk().catch(()=>new Map());
  const cached=await loadCryptoBroadCache(env);for(const [k,q] of cached)if(!map.has(k))map.set(k,q);
  // Broad discovery must not exhaust canonical deep venues. Exact probing is emergency-only.
  if(map.size<20){
    for(const fn of [bybitQuote,okxQuote,binanceQuote]){const missing=symbols.filter(x=>!map.has(x)).slice(0,18);if(!missing.length)break;const exact=await quotePool(missing,fn,2);for(const [k,v] of exact)map.set(k,v);await new Promise(r=>setTimeout(r,220));}
  }
  for(const [k,q] of map)if(!q.broadCachedAt)map.set(k,{...q,broadCachedAt:Date.now()});
  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();await saveCryptoBroadCache(env,map);return map;
}
function changeFromCandles(c){if(!Array.isArray(c)||c.length<2)return 0;const a=c.at(-2)?.close,b=c.at(-1)?.close;return a?((b-a)/a)*100:0;}
function weightedFxMove(c){if(!Array.isArray(c)||c.length<7)return changeFromCandles(c);const last=Number(c.at(-1)?.close||0);if(!(last>0))return 0;const move=n=>{const a=Number(c.at(-(n+1))?.close||0);return a>0?(last-a)/a*100:0;};return move(1)*.50+move(3)*.30+move(6)*.20;}
function forexStrengthMap(h1Map){const sum={},cnt={};for(const [sym,c] of h1Map.entries()){if(!Array.isArray(c)||c.length<2)continue;const ch=weightedFxMove(c),base=sym.slice(0,3),quote=sym.slice(3);sum[base]=(sum[base]||0)+ch;cnt[base]=(cnt[base]||0)+1;sum[quote]=(sum[quote]||0)-ch;cnt[quote]=(cnt[quote]||0)+1;}const out={};for(const k of Object.keys(sum))out[k]=sum[k]/Math.max(1,cnt[k]);return out;}
function metalSessionBias(){const h=new Date().getUTCHours();if(h>=12&&h<17)return {score:1.15,label:"LONDON_NY_OVERLAP"};if(h>=7&&h<16)return {score:.95,label:"LONDON_ACTIVE"};if(h>=13&&h<21)return {score:.95,label:"NEW_YORK_ACTIVE"};return {score:.45,label:"OFF_PEAK"};}
function indexSessionBias(symbol){const s=norm(symbol),h=new Date().getUTCHours();if(s==="JP225")return h>=0&&h<7?{score:1.10,label:"TOKYO_ACTIVE"}:{score:.35,label:"TOKYO_OFF"};if(s==="DEX")return h>=7&&h<16?{score:1.10,label:"EUROPE_ACTIVE"}:{score:.35,label:"EUROPE_OFF"};return h>=13&&h<21?{score:1.10,label:"US_CASH_WINDOW"}:{score:.40,label:"US_OFF"};}
function weightedIndexMove(c){if(!Array.isArray(c)||c.length<7)return changeFromCandles(c);const last=Number(c.at(-1)?.close||0);if(!(last>0))return 0;const mv=n=>{const a=Number(c.at(-(n+1))?.close||0);return a>0?(last-a)/a*100:0;};return mv(1)*.45+mv(3)*.35+mv(6)*.20;}
function indexBenchmark(symbol){const s=norm(symbol);return s==="NAS100"?"US500":s==="US30"?"US500":s==="US500"?"NAS100":null;}
function forexSessionBias(symbol){const s=norm(symbol),h=new Date().getUTCHours(),cc=[s.slice(0,3),s.slice(3)],asia=cc.some(x=>["JPY","AUD","NZD"].includes(x)),europe=cc.some(x=>["EUR","GBP","CHF"].includes(x)),america=cc.some(x=>["USD","CAD"].includes(x));let score=.35,label="OFF_PEAK";if(h>=0&&h<8&&asia){score=1;label="ASIA_ACTIVE";}if(h>=6&&h<13&&europe){score=Math.max(score,1);label="LONDON_ACTIVE";}if(h>=12&&h<17&&(europe||america)){score=1.15;label="LONDON_NY_OVERLAP";}if(h>=13&&h<21&&america){score=Math.max(score,.9);label=label==="LONDON_NY_OVERLAP"?label:"NEW_YORK_ACTIVE";}return {score,label};}

async function saveMarketContext(group,data,env){try{await env.TRADING_STATE?.put(CONFIG.keys.contextPrefix+group,JSON.stringify({savedAt:Date.now(),data}),{expirationTtl:300});}catch{}}
async function loadMarketContext(group,env,maxAgeMs=180000){try{const v=await env.TRADING_STATE?.get(CONFIG.keys.contextPrefix+group,"json");if(v?.savedAt&&Date.now()-Number(v.savedAt)<=maxAgeMs&&v.data)return v.data;}catch{}return null;}
async function cryptoDerivativesContext(symbol){try{const p=await bybit("/v5/market/tickers",{category:"linear",symbol:norm(symbol)}),r=p?.result?.list?.[0];if(!r||norm(r.symbol)!==norm(symbol))return {};return {fundingRate:num(r.fundingRate),openInterest:num(r.openInterest),turnover24h:num(r.turnover24h)};}catch{return {};}}
function broadRank(q){if(!q?.price)return 0;let x=0;if(q.open)x+=Math.abs((q.price-q.open)/q.open)*100;if(Number.isFinite(q.percentChange))x+=Math.abs(q.percentChange);return x;}
function selectCryptoDiverse(rows,limit=12){const out=[],seen=new Set(),add=x=>{if(x&&!seen.has(x.symbol)&&out.length<limit){seen.add(x.symbol);out.push(x);}};const idx=[0,1,2,4,7,10,14,18,24,30];for(const i of idx)add(rows[i]);const rel=[...rows].sort((a,b)=>Math.abs(Number(b.context?.relativeStrength)||0)-Math.abs(Number(a.context?.relativeStrength)||0));for(const x of rel)add(x);for(const x of rows)add(x);return out;}
async function broadScan(group,env){
  const symbols=GROUPS[group],rows=[],errors=[];
  if(group==="crypto"){const bulk=await cryptoBroadMap(symbols,env),btc=bulk.get("BTCUSDT")?.percentChange??0;for(const sym of symbols){const q=bulk.get(sym);if(q?.price){const rel=(q.percentChange??0)-btc;rows.push({symbol:sym,quote:q,strength:broadRank(q),context:{relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel))}});}else errors.push({symbol:sym,reason:"EXACT_SPOT_UNAVAILABLE"});}rows.sort((a,b)=>b.strength-a.strength);return {requested:symbols.length,rows,errors,h1Map:null};}
  let h1Map=new Map();try{h1Map=await tdBatchCandles(symbols,"1h",env,60);}catch(e){return {requested:symbols.length,rows,errors:symbols.map(symbol=>({symbol,reason:"H1_BATCH_UNAVAILABLE",error:e?.message||String(e)})),h1Map};}const fx=group==="forex"?forexStrengthMap(h1Map):{};let metalMoves={},indexMoves={};if(group==="metal")for(const sym of symbols)metalMoves[sym]=changeFromCandles(h1Map.get(sym)||[]);if(group==="index")for(const sym of symbols)indexMoves[sym]=weightedIndexMove(h1Map.get(sym)||[]);if(group==="forex")await saveMarketContext("forex",{strength:fx},env);else if(group==="metal")await saveMarketContext("metal",{moves:metalMoves},env);else if(group==="index")await saveMarketContext("index",{moves:indexMoves},env);
  for(const sym of symbols){const T=tf(h1Map.get(sym)||[]);if(!T.ready){errors.push({symbol:sym,reason:"H1_UNAVAILABLE"});continue;}let context={score:5};if(group==="forex"){const base=sym.slice(0,3),quote=sym.slice(3),d=(fx[base]||0)-(fx[quote]||0),sess=forexSessionBias(sym);context={baseStrength:fx[base]||0,quoteStrength:fx[quote]||0,strengthDiff:d,strengthNormalizedSigned:Math.max(-1,Math.min(1,d/.60)),session:sess.label,sessionScore:sess.score,score:Math.min(10,4.7+Math.abs(d)*4.2+sess.score*.75)};}else if(group==="metal"){const other=sym==="XAUUSD"?"XAGUSD":"XAUUSD",rel=(metalMoves[sym]||0)-(metalMoves[other]||0),sess=metalSessionBias();context={relativeStrength:rel,benchmark:other,session:sess.label,sessionScore:sess.score,score:Math.min(10,4.8+Math.abs(rel)*3.2+sess.score*.75)};}else if(group==="index"){const bench=indexBenchmark(sym),rel=bench?Number(indexMoves[sym]||0)-Number(indexMoves[bench]||0):0,sess=indexSessionBias(sym);context={relativeStrength:rel,benchmark:bench,session:sess.label,sessionScore:sess.score,indexMove:Number(indexMoves[sym]||0),score:Math.min(10,4.8+Math.abs(rel)*3+Math.abs(Number(indexMoves[sym]||0))*1.2+sess.score*.8)};}const raw=Math.abs((T.close-(T.ema20??T.close))/(T.atr14||1)),prior=v73Prior(sym,group),sweet=Math.max(0,1-Math.abs(raw-.35)/.85),sessionBoost=(group==="forex"||group==="metal"||group==="index")?Number(context.sessionScore||.35):sessionFit(prior),directionBoost=group==="forex"?Math.min(1.4,Math.abs(Number(context.strengthDiff||0))*3.2):group==="index"?Math.min(1.2,Math.abs(Number(context.relativeStrength||0))*2.5):group==="metal"?Math.min(1.0,Math.abs(Number(context.relativeStrength||0))*2):0,discoveryScore=sweet*2.2+Number(context.score||5)*.48+sessionBoost*.75+directionBoost*.35+Math.min(raw,1.2)*.08;rows.push({symbol:sym,quote:{source:"Twelve Data H1",price:T.close,fresh:true},strength:discoveryScore,rawStrength:raw,context});}rows.sort((a,b)=>b.strength-a.strength);return {requested:symbols.length,rows,errors,h1Map};
}
function selectForexDiverse(rows,limit){const ranked=[...(rows||[])].sort((a,b)=>(Number(b.strength)||0)-(Number(a.strength)||0)),picked=[],seen=new Set();const core=Math.min(3,limit);for(const r of ranked.slice(0,core)){picked.push(r);seen.add(r.symbol);}const used=new Set(picked.flatMap(r=>[norm(r.symbol).slice(0,3),norm(r.symbol).slice(3)]));for(const r of ranked){if(picked.length>=limit)break;if(seen.has(r.symbol))continue;const s=norm(r.symbol),b=s.slice(0,3),q=s.slice(3),overlap=(used.has(b)?1:0)+(used.has(q)?1:0);if(overlap<=1||picked.length>=limit-1){picked.push(r);seen.add(r.symbol);used.add(b);used.add(q);}}for(const r of ranked){if(picked.length>=limit)break;if(!seen.has(r.symbol)){picked.push(r);seen.add(r.symbol);}}return picked;}
async function prepareNonCryptoDeep(symbols,h1Map,env){
  const extra=["5min","15min","4h","1day"],maps=await Promise.all(extra.map(i=>tdBatchCandles(symbols,i,env,CONFIG.candleOutputSize))),out=new Map();
  for(const s of symbols)out.set(s,[maps[0].get(s)||[],maps[1].get(s)||[],h1Map.get(s)||[],maps[2].get(s)||[],maps[3].get(s)||[]]);
  return out;
}

function emptyGroup(){return {marketActive:[],signalActive:[],limitActive:[],limitPending:[],watch:[]};}
function emptyBooks(){return {forex:emptyGroup(),crypto:emptyGroup(),metal:emptyGroup(),index:emptyGroup(),updatedAt:Date.now()};}
function validExecutablePosition(p,group){
  if(!p||typeof p!=="object"||!GROUPS[group]?.includes(canonicalUserSymbol(p.symbol)))return false;
  if(!["LONG","SHORT"].includes(p.side))return false;
  if(![p.entry,p.sl,p.tp].every(v=>Number.isFinite(Number(v))&&Number(v)>0))return false;
  if(group==="crypto")return true;
  return p.executionVerified===true||!!p.brokerTicket||p.executionAuthority==="MT5";
}
function preserveLegacyOrder(p,status){return {...p,status:p.status||status,discoveredBy:p.discoveredBy||"LEGACY_PRESERVED",engineOpened:p.engineOpened||p.engine||"LEGACY",createdAt:p.createdAt||p.openedAt||Date.now()};}
function validSignalPosition(p,group){if(!p||typeof p!=="object"||!GROUPS[group]?.includes(canonicalUserSymbol(p.symbol)))return false;if(!["LONG","SHORT"].includes(p.side))return false;if(![p.entry,p.sl,p.tp].every(v=>Number.isFinite(Number(v))&&Number(v)>0))return false;return p.signalOnly===true||p.executionAuthority==="SIGNAL_ONLY";}
function normalizeBooks(v){const b=emptyBooks();if(!v||typeof v!=="object")return b;for(const g of Object.keys(GROUPS)){const src=v?.[g]||{};b[g].marketActive=Array.isArray(src.marketActive)?src.marketActive.filter(p=>validExecutablePosition(p,g)).map(p=>preserveLegacyOrder(p,"ACTIVE")):[];b[g].signalActive=Array.isArray(src.signalActive)?src.signalActive.filter(p=>validSignalPosition(p,g)).map(p=>preserveLegacyOrder(p,"ACTIVE")):[];b[g].limitActive=Array.isArray(src.limitActive)?src.limitActive.filter(p=>validExecutablePosition(p,g)).map(p=>preserveLegacyOrder(p,"ACTIVE")):[];b[g].limitPending=Array.isArray(src.limitPending)?src.limitPending.filter(p=>validExecutablePosition(p,g)).map(p=>preserveLegacyOrder(p,"PENDING")):[];b[g].watch=[];}b.updatedAt=v.updatedAt||Date.now();return b;}
async function archiveLiveOrders(env,books){try{const old=await env.TRADING_STATE.get(CONFIG.keys.orderHistory,"json"),rows=Array.isArray(old?.rows)?old.rows:[],seen=new Set(rows.map(x=>String(x?.position?.id||"")+":"+String(x?.event||"")));let changed=false;for(const g of Object.keys(GROUPS)){const b=books[g]||{};for(const p of [...(b.marketActive||[]),...(b.signalActive||[]),...(b.limitActive||[]),...(b.limitPending||[])]){const k=String(p.id||"")+":LIVE_STATE_PRESERVED";if(!p.id||seen.has(k))continue;rows.push({event:"LIVE_STATE_PRESERVED",group:g,position:p,recordedAt:Date.now(),engine:CONFIG.version});seen.add(k);changed=true;}}if(changed)await env.TRADING_STATE.put(CONFIG.keys.orderHistory,JSON.stringify({rows:rows.slice(-1000),updatedAt:Date.now()}));}catch{}}
async function getBooks(env){try{const b=normalizeBooks(await env.TRADING_STATE.get(CONFIG.keys.books,"json"));await archiveLiveOrders(env,b);return b;}catch{return emptyBooks();}}
async function saveBooks(env,b){b.updatedAt=Date.now();for(const g of Object.keys(GROUPS))b[g].watch=[];await env.TRADING_STATE.put(CONFIG.keys.books,JSON.stringify(b));}
function bookQty(p){const q=Number(p?.quantity??p?.qty);if(Number.isFinite(q)&&q>0)return {qty:q,estimated:false};const e=Number(p?.entry),sl=Number(p?.sl),risk=Number(p?.riskUsd??CONFIG.defaultRiskUsd),d=Math.abs(e-sl);return e>0&&sl>0&&risk>0&&d>0?{qty:risk/d,estimated:true}:{qty:null,estimated:true};}
async function liveBookQuote(g,p,env){try{if(g==="crypto")return await cryptoExecutionQuote(p.symbol);if(g==="forex"||g==="metal")return await tdQuote(p.symbol,env);if(g==="index")return await tdQuote(p.symbol,env);}catch{}return null;}
function enrichBookPosition(g,p,q){const o={...p},px=Number(q?.price),e=Number(p.entry),dir=p.side==="SHORT"?-1:1;o.liveSource=q?.source||null;o.liveQuoteAgeSec=Number.isFinite(Number(q?.quoteAgeSec))?Number(q.quoteAgeSec):null;if(q?.fresh===false){o.liveStale=true;return o;}if(!(px>0&&e>0))return o;o.currentPrice=px;o.liveAt=Date.now();o.liveStale=false;o.pnlPct=(px-e)/e*100*dir;if(p.status!=="PENDING"){const z=bookQty(p);if(z.qty){o.pnlUsd=(px-e)*dir*z.qty;o.pnlUsdEstimated=z.estimated||g!=="crypto";}}return o;}
async function getBooksLive(env,onlyGroup=null){const b=await getBooks(env),o=JSON.parse(JSON.stringify(b)),groups=onlyGroup&&GROUPS[onlyGroup]?[onlyGroup]:Object.keys(GROUPS),jobs=[];for(const g of groups)for(const k of ["marketActive","signalActive","limitActive","limitPending"])for(let i=0;i<(o[g]?.[k]||[]).length;i++)jobs.push((async()=>{const p=o[g][k][i],q=await liveBookQuote(g,p,env);o[g][k][i]=enrichBookPosition(g,p,q);})());await Promise.all(jobs);o.liveRefreshedAt=Date.now();o.liveRefreshedGroup=onlyGroup||"all";return o;}
async function saveScanSnapshot(group,run,env){try{await env.TRADING_STATE.put(CONFIG.keys.scanPrefix+group,JSON.stringify(run),{expirationTtl:900});}catch{}}
async function getScanSnapshot(group,env){try{return await env.TRADING_STATE.get(CONFIG.keys.scanPrefix+group,"json");}catch{return null;}}
async function appendOrderHistory(env,event){try{const old=await env.TRADING_STATE.get(CONFIG.keys.orderHistory,"json"),rows=Array.isArray(old?.rows)?old.rows:[];rows.unshift({...event,recordedAt:Date.now(),engine:CONFIG.version});await env.TRADING_STATE.put(CONFIG.keys.orderHistory,JSON.stringify({rows:rows.slice(0,250),updatedAt:Date.now()}));}catch{}}
function sideText(x){return x==="LONG"?"BUY":x==="SHORT"?"SELL":"NEUTRAL";}
function orderSourceText(x){return x==="AUTO_CRON"?"AUTO SCAN":x==="HUB_MANUAL"?"HUB MANUAL":x==="GROUP_MANUAL"?"NÚT THỊ TRƯỜNG":x==="SYMBOL_MANUAL"?"SYMBOL MANUAL":x==="COMMAND_MANUAL"?"LỆNH CHAT":x==="NEWS_MANUAL"?"NEWS CONFIRM":x==="API_RUN_NOW"?"API RUN-NOW":x==="API_HUB"?"API HUB":x==="LEGACY_PRESERVED"?"LỆNH CŨ ĐƯỢC GIỮ LẠI":String(x||"SCAN");}
function duplicate(book,sym){return [...book.marketActive,...(book.signalActive||[]),...book.limitActive,...book.limitPending].some(x=>x.symbol===sym);}
function toPos(sig,discoveredBy="SCAN"){const tp=Number.isFinite(Number(sig.tp2))?sig.tp2:sig.tp1;return {id:sig.symbol+"-"+Date.now(),symbol:sig.symbol,side:sig.side,entry:sig.entry,sl:sig.sl,tp,tp1:sig.tp1,tp2:sig.tp2,targetRR:sig.targetRR,origin:sig.action,discoveredBy,status:"ACTIVE",openedAt:Date.now(),createdAt:Date.now(),engineOpened:sig.engine,engine:sig.engine,source:sig.quote?.source,executionVerified:true,executionAuthority:sig.quote?.source||"CANONICAL_CRYPTO",quantity:Number(sig.risk?.quantity)||null,riskUsd:Number(sig.risk?.riskUsd)||CONFIG.defaultRiskUsd};}
function toSignalPos(sig,discoveredBy="SCAN",group="forex"){const tp1=Number(sig.tp1??sig.planned?.tp1),tp2=Number(sig.tp2??sig.planned?.tp2),tp=Number.isFinite(tp2)&&tp2>0?tp2:tp1,ttl=group==="forex"?12:8;return {id:`signal-${sig.symbol}-${Date.now()}`,symbol:sig.symbol,side:sig.side,entry:Number(sig.entry??sig.planned?.entry),sl:Number(sig.sl??sig.planned?.sl),tp,tp1,tp2:Number.isFinite(tp2)&&tp2>0?tp2:tp1,targetRR:Number(sig.targetRR??sig.planned?.targetRR),origin:"MARKET_SIGNAL",discoveredBy,status:"ACTIVE",openedAt:Date.now(),createdAt:Date.now(),expiresAt:Date.now()+ttl*3600000,engineOpened:sig.engine,engine:sig.engine,source:sig.analysisQuote?.source||sig.quote?.source||sig.source,executionVerified:false,executionAuthority:"SIGNAL_ONLY",signalOnly:true,riskUsd:CONFIG.defaultRiskUsd};}
function fillBooks(group,books,analyses,trigger="SCAN"){const b=books[group],newItems=[];for(const a of analyses){if(group!=="crypto"){if(a.status==="MARKET_SIGNAL"&&!duplicate(b,a.symbol)&&(b.signalActive||[]).length<CONFIG.maxMarketActive){const p=toSignalPos(a,trigger,group);b.signalActive.push(p);newItems.push(p);}continue;}if(a.status==="MARKET"&&!duplicate(b,a.symbol)&&b.marketActive.length<CONFIG.maxMarketActive){const p=toPos(a,trigger);b.marketActive.push(p);newItems.push(p);}if(a.status==="LIMIT"&&!duplicate(b,a.symbol)&&b.limitPending.length<CONFIG.maxPendingLimit&&(b.limitActive.length+b.limitPending.length)<CONFIG.maxLimitActive){const p={...toPos(a,trigger),status:"PENDING",expiresAt:Date.now()+CONFIG.pendingLimitExpiryMinutes*60000};b.limitPending.push(p);newItems.push(p);}}b.watch=[];return newItems;}
function livePositionLine(p){const kind=p.signalOnly?"MARKET SIGNAL":p.status==="PENDING"?"LIMIT CHỜ":p.origin==="LIMIT"?"LIMIT KHỚP":"MARKET",pct=Number(p.pnlPct),usd=Number(p.pnlUsd),live=Number.isFinite(pct)?`${pct>=0?"🟢":"🔴"} ${pct>=0?"+":""}${pct.toFixed(2)}%${Number.isFinite(usd)?` • ${p.pnlUsdEstimated?"~":""}${usd>=0?"+":""}${usd.toFixed(2)}`:""}`:p.status==="PENDING"?"🟡 chưa khớp":p.liveStale?`⚠️ quote stale${Number.isFinite(Number(p.liveQuoteAgeSec))?` • ${Math.round(Number(p.liveQuoteAgeSec))}s`:""}`:"⚪ chờ refresh";return `${kind} • ${p.symbol} ${sideText(p.side)} • ${live} • E ${fmtPx(p.entry)}${p.currentPrice?` → ${fmtPx(p.currentPrice)}`:""} • SL ${fmtPx(p.sl)} • TP ${fmtPx(p.tp)}`;}
function allLivePositions(books){const out=[];for(const g of ["crypto","forex","metal","index"]){const b=books?.[g];if(!b)continue;for(const p of b.marketActive||[])out.push({group:g,...p});for(const p of b.signalActive||[])out.push({group:g,...p});for(const p of b.limitActive||[])out.push({group:g,...p});}return out;}
function freshWatchFromRun(run){return (run?.analyses||[]).filter(x=>x?.status==="WATCH").sort((a,b)=>(Number(b.score)||0)-(Number(a.score)||0)).slice(0,CONFIG.maxWatch);}
async function recordShadowSetup(group,a,scanId,env){
  if(!a||!["WATCH","MARKET_PLAN","LIMIT_PLAN"].includes(a.status)||!a.planned||!["LONG","SHORT"].includes(a.side))return;
  const rr=Number(a.planned.targetRR);if(!Number.isFinite(rr)||rr<1)return;
  try{const old=await env.TRADING_STATE.get(CONFIG.keys.shadowSetups,"json"),rows=Array.isArray(old?.rows)?old.rows:[],mode=a.method?.activeMode||a.entryPolicy?.profile||"GENERIC",now=Date.now();
    const duplicate=rows.some(x=>x.status==="OPEN"&&x.symbol===a.symbol&&x.mode===mode&&now-Number(x.createdAt)<30*60000);if(duplicate)return;
    rows.unshift({id:a.symbol+"-"+now,symbol:a.symbol,group,side:a.side,mode,score:a.score??null,entry:a.planned.entry,sl:a.planned.sl,tp1:a.planned.tp1,tp2:a.planned.tp2,targetRR:a.planned.targetRR,minQualityRR:a.planned.minQualityRR??minimumQualityRR(a.method),reason:a.reason,source:a.source||null,scanId:scanId||null,createdAt:now,expiresAt:now+(group==="forex"?12:8)*3600000,status:"OPEN",calibrationStatus:a.knowledge?.calibration?.status||"UNVERIFIED"});
    await env.TRADING_STATE.put(CONFIG.keys.shadowSetups,JSON.stringify({rows:rows.slice(0,500),updatedAt:now}));}catch{}
}
async function getShadowSetups(env,symbol=null){try{const v=await env.TRADING_STATE.get(CONFIG.keys.shadowSetups,"json");const rows=Array.isArray(v?.rows)?v.rows:[];return symbol?rows.filter(x=>x.symbol===canonicalUserSymbol(symbol)):rows;}catch{return [];}}
async function getOrderHistory(env){try{const v=await env.TRADING_STATE.get(CONFIG.keys.orderHistory,"json");return {rows:Array.isArray(v?.rows)?v.rows:[],updatedAt:v?.updatedAt||null};}catch{return {rows:[],updatedAt:null};}}
async function acquireLock(env){const k=CONFIG.keys.runLock;try{const old=await env.TRADING_STATE.get(k);if(old&&Date.now()-Number(old)<CONFIG.runLockTtlSec*1000)return false;await env.TRADING_STATE.put(k,String(Date.now()),{expirationTtl:CONFIG.runLockTtlSec});return true;}catch{return true;}}
async function releaseLock(env){try{await env.TRADING_STATE.delete(CONFIG.keys.runLock);}catch{}}
async function runGroup(group,env,trigger="API_RUN_NOW"){
  if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group,version:CONFIG.version,scanId:group+"-busy-"+Date.now(),scannedAt:new Date().toISOString(),analyses:[]};
  const started=Date.now(),scanId=group+"-"+started+"-"+Math.random().toString(36).slice(2,8),scannedAt=new Date(started).toISOString();
  try{
    const budget=await ensureTdBudget(group,env);
    if(!budget.ok){const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,scanId,scannedAt,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));await saveScanSnapshot(group,out,env);return out;}
    const broad=await broadScan(group,env),analyses=[];let deepAttempted=0,skippedUnavailable=[];
    const existingBooks=await getBooks(env),liveSymbols=new Set([...(existingBooks[group]?.marketActive||[]),...(existingBooks[group]?.signalActive||[]),...(existingBooks[group]?.limitActive||[]),...(existingBooks[group]?.limitPending||[])].map(x=>canonicalUserSymbol(x.symbol)));
    const entryRows=broad.rows.filter(x=>!liveSymbols.has(canonicalUserSymbol(x.symbol)));
    if(group==="crypto"){
      const shortlist=selectCryptoDiverse(entryRows,CONFIG.deepShortlist),valid=[];
      for(const c of shortlist){
        if(Date.now()-started>CONFIG.scanDeadlineMs-2500)break;deepAttempted++;let b;
        try{b=await cryptoDeepBundle(c.symbol,{preferAnalysis:!!c.quote?.analysisOnly,preferredBroadSource:c.quote?.source});}catch(e){skippedUnavailable.push({symbol:c.symbol,reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)});await new Promise(r=>setTimeout(r,CONFIG.cryptoDeepCooldownMs));continue;}
        const dc=await cryptoDerivativesContext(c.symbol),a=await deepAnalyze(c.symbol,env,b.candles,b.quote,b.source,{...(c.context||{}),...dc});valid.push(a);
        await new Promise(r=>setTimeout(r,CONFIG.cryptoDeepCooldownMs));const ac=valid.filter(x=>["MARKET","LIMIT","MARKET_PLAN","LIMIT_PLAN"].includes(x?.status)).length;if(valid.length>=CONFIG.cryptoDeepTarget&&ac>=CONFIG.cryptoActionTarget)break;if(valid.length>=CONFIG.cryptoDeepMax)break;
      }
      valid.sort((a,b)=>actionableRank(b)-actionableRank(a));analyses.push(...valid.slice(0,CONFIG.maxCandidates));
    }else{
      const deepLimit=group==="forex"?CONFIG.deepNonCryptoCandidates:CONFIG.maxCandidates,candidates=group==="forex"?selectForexDiverse(entryRows,deepLimit):entryRows.slice(0,deepLimit),tmp=[];let prepared=new Map();try{prepared=await prepareNonCryptoDeep(candidates.map(c=>c.symbol),broad.h1Map,env);}catch{}
      for(const c of candidates){if(Date.now()-started>CONFIG.scanDeadlineMs)break;deepAttempted++;const pc=prepared.get(c.symbol);if(!pc)tmp.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"ANALYSIS_DATA_UNAVAILABLE"});else tmp.push(await deepAnalyze(c.symbol,env,pc,null,"Twelve Data",c.context||{}));}
      tmp.sort((a,b)=>actionableRank(b)-actionableRank(a));analyses.push(...tmp.slice(0,CONFIG.maxCandidates));
    }
    const books=existingBooks,newItems=fillBooks(group,books,analyses,trigger);await saveBooks(env,books);for(const a of analyses)await recordShadowSetup(group,a,scanId,env);
    const out={ok:true,version:CONFIG.version,group,scanId,scannedAt,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:deepAttempted,deepOk:analyses.filter(a=>a.ok!==false).length,newCount:newItems.length,newItems,scanTrigger:trigger,analyses,diagnostics:{broadErrors:broad.errors,deepAttempted,skippedUnavailable,liveSymbolsSkipped:[...liveSymbols],tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};
    await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));await saveScanSnapshot(group,out,env);return out;
  }finally{await releaseLock(env);}
}
function canonicalUserSymbol(symbol){const x=norm(symbol);if(x==="TON"||x==="TONUSDT")return "GRAMUSDT";return x;}
async function runSymbol(symbol,env){
  const s=canonicalUserSymbol(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};
  if(type==="crypto"){let b;try{b=await cryptoDeepBundle(s,{preferAnalysis:true});}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)};}let context={score:5};try{const bulk=await cryptoBulk(),sq=b.quote?.percentChange??bulk.get(s)?.percentChange??0,bq=s==="BTCUSDT"?sq:(bulk.get("BTCUSDT")?.percentChange??0),rel=sq-bq;context={relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel)),...(await cryptoDerivativesContext(s))};}catch{}const a=await deepAnalyze(s,env,b.candles,b.quote,b.source,context);if(b.quote)a.analysisQuote=b.quote;return a;}
  if(type==="forex"){let cached=await loadMarketContext("forex",env),fx=cached?.strength||null,h1;if(fx){h1=await tdBatchCandles([s],"1h",env,60);}else{h1=await tdBatchCandles(FOREX,"1h",env,60);fx=forexStrengthMap(h1);await saveMarketContext("forex",{strength:fx},env);}const base=s.slice(0,3),quote=s.slice(3),d=(fx[base]||0)-(fx[quote]||0),context={baseStrength:fx[base]||0,quoteStrength:fx[quote]||0,strengthDiff:d,strengthNormalizedSigned:Math.max(-1,Math.min(1,d/.60)),session:forexSessionBias(s).label,sessionScore:forexSessionBias(s).score,score:Math.min(10,4.7+Math.abs(d)*4.2+forexSessionBias(s).score*.75),contextCached:!!cached},extra=await Promise.all(["5min","15min","4h","1day"].map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=[extra[0].get(s)||[],extra[1].get(s)||[],h1.get(s)||[],extra[2].get(s)||[],extra[3].get(s)||[]];let q=null;try{q=await tdQuote(s,env);}catch{}const a=await deepAnalyze(s,env,candles,q,"Twelve Data direct + cached 28-pair strength",context);if(q)a.analysisQuote=q;return a;}
  if(type==="metal"){let cached=await loadMarketContext("metal",env),moves=cached?.moves||null,h1;if(moves){h1=await tdBatchCandles([s],"1h",env,60);}else{h1=await tdBatchCandles(METALS,"1h",env,60);moves={};for(const x of METALS)moves[x]=changeFromCandles(h1.get(x)||[]);await saveMarketContext("metal",{moves},env);}const other=s==="XAUUSD"?"XAGUSD":"XAUUSD",rel=(moves[s]||0)-(moves[other]||0),context={relativeStrength:rel,benchmark:other,score:Math.min(10,5+Math.abs(rel)*3),contextCached:!!cached},extra=await Promise.all(["5min","15min","4h","1day"].map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=[extra[0].get(s)||[],extra[1].get(s)||[],h1.get(s)||[],extra[2].get(s)||[],extra[3].get(s)||[]];let q=null;try{q=await tdQuote(s,env);}catch{}const a=await deepAnalyze(s,env,candles,q,"Twelve Data direct + cached metal relative",context);if(q)a.analysisQuote=q;return a;}
  const maps=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=maps.map(m=>m.get(s)||[]);let q=null;try{q=await tdQuote(s,env);}catch{}const sess=indexSessionBias(s),context={session:sess.label,sessionScore:sess.score,score:Math.min(10,5+sess.score*.8)};const a=await deepAnalyze(s,env,candles,q,q?.source||"Verified native Index",context);if(q)a.analysisQuote=q;return a;
}
async function telegram(env,method,payload){if(!env.TELEGRAM_BOT_TOKEN)throw new Error("TELEGRAM_BOT_TOKEN missing");const r=await fetchTimeout(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)}),p=await r.json();if(!p.ok)throw new Error(p.description||"Telegram error");return p;}
function telegramSafeText(text){const x=String(text??"");return x.length<=3900?x:x.slice(0,3860)+"\n… đã rút gọn";}
async function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text:telegramSafeText(text),reply_markup,disable_web_page_preview:true});}
function baseKeyboard(){return {inline_keyboard:[[{text:"📡 SIGNAL",callback_data:"signal"}],[{text:"🏦 PROP",callback_data:"prop"},{text:"👤 CÁ NHÂN",callback_data:"personal"}],[{text:"🔎 SYMBOL",callback_data:"symbols"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 LIVE ORDERS",callback_data:"live"}]]};}
function signalKeyboard(){return {inline_keyboard:[[{text:"🧭 QUÉT TẤT CẢ / TOP SETUPS",callback_data:"hub"}],[{text:"💱 FOREX",callback_data:"scan:forex"},{text:"🪙 CRYPTO",callback_data:"scan:crypto"}],[{text:"🥇 METAL",callback_data:"scan:metal"},{text:"📊 INDEX CASH",callback_data:"scan:index"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}
function propKeyboard(){return {inline_keyboard:[[{text:"🟣 HYROTRADER",callback_data:"prop:hyro"},{text:"🔵 BREAKOUT",callback_data:"prop:breakout"}],[{text:"📚 LỆNH PROP",callback_data:"prop:orders"},{text:"🛡️ RISK PROP",callback_data:"prop:risk"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}
function personalKeyboard(){return {inline_keyboard:[[{text:"🖥️ MT5 CÁ NHÂN",callback_data:"personal:mt5"}],[{text:"📚 LỆNH CÁ NHÂN",callback_data:"personal:orders"},{text:"🛡️ RISK CÁ NHÂN",callback_data:"personal:risk"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}
function symbolMarketKeyboard(){return {inline_keyboard:[[{text:"💱 Forex",callback_data:"symmarket:forex"},{text:"🪙 Crypto",callback_data:"symmarket:crypto"}],[{text:"🥇 Metal",callback_data:"symmarket:metal"},{text:"📊 Index Cash",callback_data:"symmarket:index"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}
function symbolListFor(group){return GROUPS[group]||[];}
function symbolPageKeyboard(group,page=0){const all=symbolListFor(group),size=12,pages=Math.max(1,Math.ceil(all.length/size)),p=Math.max(0,Math.min(pages-1,Number(page)||0)),slice=all.slice(p*size,p*size+size),rows=[];for(let i=0;i<slice.length;i+=2)rows.push(slice.slice(i,i+2).map(sym=>({text:sym,callback_data:"sym:"+group+":"+sym})));const nav=[];if(p>0)nav.push({text:"⬅️",callback_data:"sympage:"+group+":"+(p-1)});nav.push({text:(p+1)+"/"+pages,callback_data:"noop"});if(p<pages-1)nav.push({text:"➡️",callback_data:"sympage:"+group+":"+(p+1)});rows.push(nav);rows.push([{text:"↩️ Chọn thị trường",callback_data:"symbols"},{text:"📡 SIGNAL",callback_data:"signal"}]);return {inline_keyboard:rows};}
function groupKeyboard(group,run){const rows=baseKeyboard().inline_keyboard,pending=freshWatchFromRun(run).filter(w=>w.reason==="NEWS_CONTEXT_REQUIRED").slice(0,3);if(pending.length)rows.unshift(pending.map(w=>({text:"✅ Tin OK "+w.symbol,callback_data:"news:"+group+":"+w.symbol})));return {inline_keyboard:rows};}
function signalNotifyKeyboard(group,symbol=null){const rows=[];if(symbol)rows.push([{text:"🔎 "+symbol,callback_data:"symbol:"+group+":"+symbol},{text:"📡 "+groupTitle(group).replace(/^[^ ]+ /,""),callback_data:"signal:scan:"+group}]);else rows.push([{text:"📡 Quét lại",callback_data:"signal:scan:"+group}]);rows.push([{text:"📚 Live "+groupTitle(group).replace(/^[^ ]+ /,""),callback_data:"live:"+group},{text:"🏠 Hub",callback_data:"menu"}]);return {inline_keyboard:rows};}
function signalEventText(kind,p,extra={}){const group=extra.group||"crypto",side=sideText(p?.side),entry=fmtPx(p?.entry),sl=fmtPx(p?.sl),tp1=fmtPx(p?.tp1),tp2=fmtPx(p?.tp2||p?.tp),rr=Number(p?.targetRR);const head=p?.signalOnly&&kind==="TP"?"✅ SIGNAL TP • THEORETICAL":p?.signalOnly&&kind==="SL"?"🛑 SIGNAL SL • THEORETICAL":kind==="LIMIT_FILLED"?"🔵 LIMIT KHỚP • LIVE":kind==="TP"?"✅ TP DONE":kind==="SL"?"🛑 SL HIT":kind==="LIMIT_NEW"?"🟡 LIMIT MỚI • ĐANG CHỜ":"🟢 MARKET • LIVE";const L=[head,groupTitle(group)+" • "+(p?.symbol||"—")+" • "+side,"━━━━━━━━━━━━━━"];if(p?.signalOnly)L.push("ℹ️ SIGNAL-ONLY • theoretical outcome • not broker fill");if(kind==="TP"||kind==="SL"){const mv=Number(extra.closePrice)>0&&Number(p?.entry)>0?(Number(extra.closePrice)-Number(p.entry))/Number(p.entry)*100*(p.side==="SHORT"?-1:1):null;L.push("📍 Entry "+entry,"🏁 Close "+fmtPx(extra.closePrice)+(Number.isFinite(mv)?` • ${mv>=0?"+":""}${mv.toFixed(2)}%`:""));}else{L.push("🎯 Entry "+entry,"🛡 SL "+sl,"💰 TP1 "+tp1+" • TP2 "+tp2+(Number.isFinite(rr)?" • RR "+rr.toFixed(2):""));if(kind!=="LIMIT_NEW")L.push("🔄 Mở 📚 Live Orders để refresh P/L % + USD");}if(p?.discoveredBy)L.push("⚙️ "+orderSourceText(p.discoveredBy));return L.join("\n");}
function hubKeyboard(h){const rows=baseKeyboard().inline_keyboard,p=[];for(const [g,r] of Object.entries(h?.runs||{}))for(const w of freshWatchFromRun(r))if(w.reason==="NEWS_CONTEXT_REQUIRED"&&p.length<3)p.push({text:"✅ Tin OK "+w.symbol,callback_data:"news:"+g+":"+w.symbol});if(p.length)rows.unshift(p);return {inline_keyboard:rows};}
function groupTitle(g){return g==="forex"?"💱 FOREX":g==="crypto"?"🪙 CRYPTO":g==="index"?"📊 INDEX CASH":"🥇 METAL";}
function fmtPx(v){const n=Number(v);if(!Number.isFinite(n))return "—";if(Math.abs(n)>=1000)return n.toFixed(2);if(Math.abs(n)>=10)return n.toFixed(4);if(Math.abs(n)>=1)return n.toFixed(5);return n.toPrecision(6);}
function reasonText(r){return ({HTF_METHOD_ALIGNMENT_REQUIRED:"Chờ phương pháp riêng + HTF đồng thuận",HTF_ALIGNMENT_REQUIRED:"Chờ D1/H4/H1 đồng thuận",M15_LOCATION_REQUIRED:"Chờ giá vào vùng M15 đẹp",M5_MSS_DISPLACEMENT_RETEST_REQUIRED:"Chờ trigger M5 phù hợp profile",STRUCTURAL_SL_REQUIRED:"Chưa có SL cấu trúc",CLEAN_TARGET_REQUIRED:"Chưa có mục tiêu thanh khoản đủ tốt",NEWS_CONTEXT_REQUIRED:"Chờ tin/context",EXECUTION_QUOTE_REQUIRED:"Kế hoạch đạt cấu trúc; chờ giá execution thật",FINAL_QUOTE_REQUIRED:"Chờ giá execution",FINAL_QUOTE_STALE:"Giá execution cũ",EXECUTION_COST_TOO_HIGH:"Spread/chi phí cao",RR_QUALITY_REQUIRED:"RR cấu trúc chưa đủ tốt",LIMIT_GEOMETRY_REQUIRED:"Vùng LIMIT chưa đúng khoảng cách/retest",MARKET_GEOMETRY_REQUIRED:"Giá MARKET đã chạy xa trigger",TIMEFRAME_DATA_REQUIRED:"Thiếu timeframe",ANALYSIS_DATA_UNAVAILABLE:"Thiếu dữ liệu"})[r]||"Chờ thêm xác nhận";}
function stageText(a){if(a.status==="MARKET_SIGNAL")return "⚡ MARKET SIGNAL";if(a.status==="MARKET")return "🟢 MARKET EXEC";if(a.status==="LIMIT")return "🟡 LIMIT EXEC";if(a.status==="MARKET_PLAN"||a.planned?.mode==="MARKET")return "🟢 MARKET PLAN";if(a.status==="LIMIT_PLAN"||a.planned?.mode==="LIMIT"||a.planned?.mode==="INDICATIVE_LIMIT")return "🟡 LIMIT PLAN";if(a.reason==="NEWS_CONTEXT_REQUIRED")return "🟠 ARMED";if(a.reason==="EXECUTION_QUOTE_REQUIRED"||a.reason==="FINAL_QUOTE_REQUIRED")return "🔵 READY";if(a.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")return "🟣 SETUP";return "⚪ WATCH";}
function posLine(p){return `${p.symbol} ${sideText(p.side)} • E ${fmtPx(p.entry)} • SL ${fmtPx(p.sl)} • TP ${fmtPx(p.tp)}`;}
function planMetricText(symbol,p){if(!p)return null;const cur=Number(p.currentPrice),entry=Number(p.entry),dist=Number.isFinite(cur)&&Number.isFinite(entry)?Math.abs(cur-entry):null,g=p.geometry||p.marketGeometry||{};let x=[];if(Number.isFinite(dist))x.push("Δ "+fmtPx(dist));if(Number.isFinite(g.distanceATR))x.push(g.distanceATR+" ATR");if(Number.isFinite(g.chaseATR))x.push("chase "+g.chaseATR+" ATR");if(Number.isFinite(p.confluence))x.push("confluence "+p.confluence);return x.length?x.join(" • "):null;}
function watchLine(w){let x=`${w.symbol} ${sideText(w.side)} • ${reasonText(w.reason)}`;if(Number.isFinite(w.score))x+=` • ${w.score}/100`;if(w.planned){const tag=w.planned.indicative?"Tham khảo":"Kế hoạch";x+=`
   ↳ ${tag}: E~${fmtPx(w.planned.entry)} • SL~${fmtPx(w.planned.sl)} • TP~${fmtPx(w.planned.tp2||w.planned.tp1)} • RR~${Number(w.planned.targetRR||0).toFixed(2)}`;if(w.planned.entryStyle)x+=`
   ↳ Entry style: ${w.planned.entryStyle}`;const mt=planMetricText(w.symbol,w.planned);if(mt)x+=`
   ↳ Geometry: ${mt}`}if(w.method?.profile)x+=`
   ↳ Method: ${w.method.profile}`;return x;}
function singleAnalysisText(a){
  if(!a)return "⛔ Không có kết quả phân tích.";
  if(a.ok===false)return `⛔ ${a.symbol||"SYMBOL"} • ${reasonText(a.reason)}\n${a.error?"Chi tiết: "+a.error:""}`;
  const L=[`🔎 ${a.symbol} • ${stageText(a)}${Number.isFinite(a.score)?" • "+a.score+"/100":""}`,`Hướng: ${sideText(a.side)}`];
  if(a.method?.profile)L.push(`Profile: ${a.method.profile}`);if(a.method?.activeMode)L.push(`Active route: ${a.method.activeMode}${a.method.allowedModes?.length>1?" (allowed: "+a.method.allowedModes.join("/")+")":""}`);if(a.knowledge?.calibration?.status)L.push(`Calibration: ${a.knowledge.calibration.status}`);
  if(a.entryPolicy?.profile)L.push(`Profile engine: ${a.entryPolicy.profile}`);
  if(a.status==="MARKET"||a.status==="LIMIT"){L.push("",`✅ LỆNH EXECUTABLE ${a.status}`,`Entry ${fmtPx(a.entry)} • SL ${fmtPx(a.sl)}`,`TP1 ${fmtPx(a.tp1)} • TP2 ${fmtPx(a.tp2)} • RR ${Number(a.targetRR||0).toFixed(2)}`);}
  else if(a.status==="MARKET_SIGNAL"){L.push("",`⚡ MARKET SIGNAL • SIGNAL-ONLY`,`Entry ${fmtPx(a.entry)} • SL ${fmtPx(a.sl)}`,`TP1 ${fmtPx(a.tp1)} • TP2 ${fmtPx(a.tp2)} • RR ${Number(a.targetRR||0).toFixed(2)}`,`Session ${a.context?.session||"—"} • không phải broker fill`);}
  else if(a.planned){const tag=a.planned.indicative?"📐 ENTRY THAM KHẢO — chưa phải lệnh":"🎯 KẾ HOẠCH ENTRY";L.push("",tag,`E~${fmtPx(a.planned.entry)} • SL~${fmtPx(a.planned.sl)}`,`TP1~${fmtPx(a.planned.tp1)} • TP2~${fmtPx(a.planned.tp2)} • RR~${Number(a.planned.targetRR||0).toFixed(2)}`);if(a.planned.entryStyle)L.push(`Style: ${a.planned.entryStyle}`);const mt=planMetricText(a.symbol,a.planned);if(mt)L.push(`Geometry: ${mt}`);if(a.basisReference)L.push(`⚠️ Giá plan dùng leader ${a.executionLeader}; phải refresh ${a.symbol} trước execution.`);}
  L.push("",`Trạng thái: ${a.status==="WATCH"?reasonText(a.reason):a.status}`);if(a.source)L.push(`Data: ${a.source}`);const q=a.quote||a.analysisQuote;if(q?.price)L.push(`Giá nguồn: ${fmtPx(q.price)}${Number.isFinite(q.quoteAgeSec)?" • age "+q.quoteAgeSec+"s":""}${q.executionVerified?" • execution verified":" • analysis only"}`);if(a.context?.benchmark)L.push(`Context: đối chiếu ${a.context.benchmark}${a.context.smtSignal&&a.context.smtSignal!=="NONE"?" • SMT "+a.context.smtSignal:""}`);
  return L.join("\n");
}
function freshPlanFromRun(run,kind){return (run?.analyses||[]).filter(a=>a?.planned&&(kind==="market"?(a.status==="MARKET_SIGNAL"||a.status==="MARKET_PLAN"||a.planned.mode==="MARKET"):(a.status==="LIMIT_PLAN"||a.planned.mode==="LIMIT"||a.planned.mode==="INDICATIVE_LIMIT"))).sort((a,b)=>actionableRank(b)-actionableRank(a));}
function summary(group,books,run=null){
  const b=books[group],marketPlans=freshPlanFromRun(run,"market"),limitPlans=freshPlanFromRun(run,"limit"),watch=(run?.analyses||[]).filter(a=>a?.status==="WATCH"&&!a.planned).sort((a,b)=>(Number(b.score)||0)-(Number(a.score)||0)).slice(0,CONFIG.maxWatch),L=[groupTitle(group)];
  if(run?.scannedAt)L.push("🕒 Quét mới: "+run.scannedAt);
  L.push("","🟢 MARKET EXEC ĐANG CHẠY "+b.marketActive.length+"/"+CONFIG.maxMarketActive);if(b.marketActive.length)b.marketActive.forEach((p,i)=>L.push((i+1)+". "+livePositionLine(p)));else L.push("Trống");
  L.push("","⚡ MARKET SIGNAL ĐANG THEO DÕI "+(b.signalActive||[]).length+"/"+CONFIG.maxMarketActive);if((b.signalActive||[]).length)b.signalActive.forEach((p,i)=>L.push((i+1)+". "+livePositionLine(p)+" • SIGNAL-ONLY"));else L.push("Trống");
  L.push("","🔵 LIMIT ĐÃ KHỚP / ĐANG CHẠY "+b.limitActive.length+"/"+CONFIG.maxLimitActive);if(b.limitActive.length)b.limitActive.forEach((p,i)=>L.push((i+1)+". "+livePositionLine(p)));else L.push("Trống");
  L.push("","🎯 MARKET PLAN "+marketPlans.length);if(marketPlans.length)marketPlans.slice(0,3).forEach((a,i)=>L.push((i+1)+". "+watchLine(a)));else L.push("Trống");
  L.push("","📐 LIMIT PLAN "+limitPlans.length);if(limitPlans.length)limitPlans.slice(0,3).forEach((a,i)=>L.push((i+1)+". "+watchLine(a)));else L.push("Trống");
  L.push("","🟡 LIMIT ĐANG CHỜ "+b.limitPending.length+"/"+CONFIG.maxPendingLimit);if(b.limitPending.length)b.limitPending.forEach((p,i)=>L.push((i+1)+". "+livePositionLine(p)));else L.push("Trống");
  L.push("","👀 WATCH THUẦN "+watch.length);if(watch.length)watch.forEach((a,i)=>L.push((i+1)+". "+watchLine(a)));else L.push("Trống");
  if(run?.status==="RATE_BUDGET_WAIT"){L.push("⏱ Không dùng setup cũ. Chờ quota ~"+(run.retryAfterSec??60)+"s.");return L.join("\n");}
  if(run?.status==="BUSY"){L.push("⏳ Một lượt quét khác đang chạy. Không hiển thị setup cũ.");return L.join("\n");}
  if(run)L.push("🔍 Coverage "+run.broadOk+"/"+run.requested+" • Deep "+run.deepOk+"/"+run.deepRequested+" • Record Live mới "+run.newCount,"🆔 Scan "+run.scanId);return L.join("\n");
}
async function sendGroup(group,env,chatId){await sendText(env,"⏳ Đang quét MỚI "+group.toUpperCase()+"...",chatId);const run=await runGroup(group,env,"GROUP_MANUAL"),books=await getBooksLive(env,group);return sendText(env,summary(group,books,run),chatId,groupKeyboard(group,run));}
function hubRank(a){return actionableRank(a);}
async function runHub(env,trigger="API_HUB"){const t=Date.now(),runs={};for(const g of ["crypto","forex","metal","index"])runs[g]=await runGroup(g,env,trigger);const top=Object.entries(runs).flatMap(([group,r])=>(r.analyses||[]).map(a=>({...a,group,scanId:r.scanId,scannedAt:r.scannedAt}))).sort((a,b)=>hubRank(b)-hubRank(a)).slice(0,7);const books=await getBooks(env);return {ok:true,version:CONFIG.version,books,hubScanId:"hub-"+t+"-"+Math.random().toString(36).slice(2,8),scannedAt:new Date(t).toISOString(),runs,top};}
function hubSummary(h){const live=allLivePositions(h.books),L=["🧭 TRADING HUB "+CONFIG.version,"🕒 QUÉT MỚI: "+h.scannedAt,"🆔 "+h.hubScanId,"","📚 LIVE POSITIONS "+live.length];if(live.length)live.forEach((p,i)=>L.push((i+1)+". "+groupTitle(p.group)+" • "+livePositionLine(p)));else L.push("Trống");L.push("","🔥 TOP SETUPS MỚI CỦA LẦN QUÉT NÀY");if(!h.top.length)L.push("Không có setup mới đạt chuẩn lúc này.");h.top.slice(0,5).forEach((a,i)=>{let line=(i+1)+". "+a.symbol+" "+sideText(a.side)+" • "+stageText(a)+" • "+(Number(a.score)||0)+"/100";if(a.method?.profile||a.method?.families?.length)line+="\n   ↳ Profile: "+(a.method?.profile||a.method?.families?.[0]);if(a.method?.activeMode)line+="\n   ↳ Route: "+a.method.activeMode;if(a.planned){const tag=a.planned.indicative?"Entry tham khảo":"Kế hoạch";line+="\n   ↳ "+tag+": E~"+fmtPx(a.planned.entry)+" • SL~"+fmtPx(a.planned.sl)+" • TP~"+fmtPx(a.planned.tp2||a.planned.tp1)+" • RR~"+Number(a.planned.targetRR||0).toFixed(2);}line+="\n   ↳ "+(a.status==="MARKET_SIGNAL"?"Signal advisory fresh — SIGNAL-ONLY":a.status==="MARKET"||a.status==="LIMIT"?"Đủ gate execution":a.status==="MARKET_PLAN"||a.status==="LIMIT_PLAN"?"Kế hoạch kỹ thuật hợp lệ — chờ execution authority":reasonText(a.reason));L.push(line);});L.push("","Điểm Hub = độ hoàn thiện setup, KHÔNG phải xác suất thắng.");for(const g of ["forex","crypto","metal","index"]){const r=h.runs[g];L.push(groupTitle(g)+" • "+(r.status==="RATE_BUDGET_WAIT"?"đợi quota — không dùng setup cũ":r.status==="BUSY"?"BUSY — không dùng setup cũ":r.broadOk+"/"+r.requested+" • deep "+r.deepOk+"/"+r.deepRequested));}return L.join("\n");}
async function sendHub(env,chatId){await sendText(env,"⏳ HUB đang QUÉT MỚI Crypto + Forex + Metal + Index Cash...",chatId);const h=await runHub(env,"HUB_MANUAL");return sendText(env,hubSummary(h),chatId,hubKeyboard(h));}
function booksSummary(books){const L=["📚 LIVE ORDERS — LƯU BỀN QUA UPDATE BOT"];for(const g of ["forex","crypto","metal","index"]){const b=books[g];L.push("",groupTitle(g)+" • MARKET EXEC "+b.marketActive.length+" • MARKET SIGNAL "+(b.signalActive||[]).length+" • LIMIT ACTIVE "+b.limitActive.length+" • LIMIT CHỜ "+b.limitPending.length);for(const p of b.marketActive)L.push("• "+livePositionLine(p));for(const p of b.signalActive||[])L.push("• "+livePositionLine(p)+" • SIGNAL-ONLY");for(const p of b.limitActive)L.push("• "+livePositionLine(p));for(const p of b.limitPending)L.push("• "+livePositionLine(p));}L.push("","WATCH/SETUP không nằm trong Books; Hub quét setup mới nhưng LIVE positions luôn được hiển thị riêng.");return L.join("\n");}
async function lifecycleSignalGroups(env,books){let changed=false;for(const group of ["forex","metal","index"]){const b=books[group],keep=[];for(const p of b.signalActive||[]){if(p.expiresAt&&Date.now()>Number(p.expiresAt)){changed=true;await appendOrderHistory(env,{event:"SIGNAL_EXPIRED",group,position:p});continue;}try{const q=await liveBookQuote(group,p,env);if(!q||q.fresh===false){keep.push(p);continue;}const px=Number(q.price),hitTP=p.side==="LONG"?px>=Number(p.tp):px<=Number(p.tp),hitSL=p.side==="LONG"?px<=Number(p.sl):px>=Number(p.sl);if(hitTP||hitSL){changed=true;await appendOrderHistory(env,{event:hitTP?"SIGNAL_TP":"SIGNAL_SL",group,position:p,closePrice:px,source:q.source});await sendText(env,signalEventText(hitTP?"TP":"SL",p,{group,closePrice:px}),undefined,signalNotifyKeyboard(group,p.symbol)).catch(()=>{});}else keep.push(p);}catch{keep.push(p);}}b.signalActive=keep;}return changed;}
async function lifecycle(env){
  const books=await getBooks(env),b=books.crypto;let changed=await lifecycleSignalGroups(env,books),pending=[];
  for(const p of b.limitPending){
    if(p.expiresAt&&Date.now()>p.expiresAt){changed=true;await appendOrderHistory(env,{event:"LIMIT_EXPIRED",group:"crypto",position:p});continue;}
    try{const q=await cryptoExecutionQuote(p.symbol),px=q.price,fill=p.side==="LONG"?px<=p.entry:px>=p.entry;if(fill&&b.limitActive.length<CONFIG.maxLimitActive){p.status="ACTIVE";p.openedAt=Date.now();b.limitActive.push(p);changed=true;await appendOrderHistory(env,{event:"LIMIT_FILLED",group:"crypto",position:p,price:px});await sendText(env,signalEventText("LIMIT_FILLED",p,{group:"crypto"}),undefined,signalNotifyKeyboard("crypto",p.symbol)).catch(()=>{});}else pending.push(p);}catch{pending.push(p);}
  }
  b.limitPending=pending;
  for(const key of ["marketActive","limitActive"]){const keep=[];for(const p of b[key]){try{const q=await cryptoExecutionQuote(p.symbol),px=q.price,hitTP=p.side==="LONG"?px>=p.tp:px<=p.tp,hitSL=p.side==="LONG"?px<=p.sl:px>=p.sl;if(hitTP||hitSL){changed=true;await appendOrderHistory(env,{event:hitTP?"TP":"SL",group:"crypto",position:p,closePrice:px});await sendText(env,signalEventText(hitTP?"TP":"SL",p,{group:"crypto",closePrice:px}),undefined,signalNotifyKeyboard("crypto",p.symbol)).catch(()=>{});}else keep.push(p);}catch{keep.push(p);}}b[key]=keep;}
  if(changed)await saveBooks(env,books);
}
async function notifyNewCryptoOrders(run,env){for(const p of run?.newItems||[]){const pending=p.status==="PENDING";await sendText(env,signalEventText(pending?"LIMIT_NEW":"MARKET_NEW",p,{group:"crypto"}),undefined,signalNotifyKeyboard("crypto",p.symbol)).catch(()=>{});}}
async function autoScanCrypto(env){const run=await runGroup("crypto",env,"AUTO_CRON");await notifyNewCryptoOrders(run,env);return run;}
async function notifySignalPlans(group,run,env){
  const persistedSignals=new Set((run?.newItems||[]).filter(p=>p?.signalOnly&&p?.origin==="MARKET_SIGNAL").map(p=>canonicalUserSymbol(p.symbol)));
  const plans=(run?.analyses||[]).filter(a=>a?.planned&&["MARKET_SIGNAL","MARKET_PLAN","LIMIT_PLAN"].includes(a.status)&&(a.status!=="MARKET_SIGNAL"||persistedSignals.has(canonicalUserSymbol(a.symbol)))).sort((a,b)=>actionableRank(b)-actionableRank(a)).slice(0,2);
  for(const a of plans){
    const mode=a.status==="MARKET_SIGNAL"||a.status==="MARKET_PLAN"?"MARKET":"LIMIT",entry=Number(a.planned?.entry),sig=[group,a.symbol,a.side,mode,Number.isFinite(entry)?entry.toPrecision(6):"na"].join(":");
    const key="v771816:signal:auto_notify:"+sig;let seen=null;try{seen=await env.TRADING_STATE?.get(key);}catch{}if(seen)continue;
    const rr=Number(a.planned?.targetRR||0).toFixed(2),marketNow=a.status==="MARKET_SIGNAL",txt=[marketNow?"⚡ MARKET SIGNAL • "+groupTitle(group):"📡 SIGNAL PLAN • "+groupTitle(group),"━━━━━━━━━━━━━━",(mode==="MARKET"?"🟢":"🟡")+" "+a.symbol+" • "+sideText(a.side)+" • "+mode,"🎯 Entry "+fmtPx(a.planned.entry),"🛡 SL "+fmtPx(a.planned.sl),"💰 TP1 "+fmtPx(a.planned.tp1)+" • TP2 "+fmtPx(a.planned.tp2||a.planned.tp1)+" • RR "+rr,"⭐ Score "+(Number(a.score)||0)+"/100"+(a.method?.profile?" • "+a.method.profile:""),marketNow?"ℹ️ SIGNAL-ONLY • giá phân tích fresh • không phải broker fill":"ℹ️ Plan kỹ thuật • chờ execution authority thật"].join("\n");
    let sent=false;try{await sendText(env,txt,undefined,signalNotifyKeyboard(group,a.symbol));sent=true;}catch{}if(sent)try{await env.TRADING_STATE?.put(key,String(Date.now()),{expirationTtl:1800});}catch{}
  }
}
async function autoScanSignalGroup(group,env){const run=await runGroup(group,env,"AUTO_CRON");await notifySignalPlans(group,run,env);return run;}
async function setupWebhook(req,env){const u=new URL(req.url),url=`${u.origin}/telegram/webhook`,payload={url,allowed_updates:["message","callback_query"]};if(env.TELEGRAM_WEBHOOK_SECRET)payload.secret_token=env.TELEGRAM_WEBHOOK_SECRET;return telegram(env,"setWebhook",payload);}
function verifyTelegram(req,env){return !env.TELEGRAM_WEBHOOK_SECRET||req.headers.get("x-telegram-bot-api-secret-token")===env.TELEGRAM_WEBHOOK_SECRET;}
async function handleTelegram(req,env){
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  const u=await req.json(),chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID,cb=u?.callback_query?.data,text=String(u?.message?.text||"");
  if(u?.callback_query?.id)telegram(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  if(cb==="menu"||text==="/start"||text==="/menu")await sendText(env,"🏠 TRADING HUB\n\nChọn khu vực:",chatId,baseKeyboard());
  else if(cb==="signal")await sendText(env,"📡 SIGNAL\n\nMỗi lần bấm quét sẽ lấy dữ liệu thị trường mới. Chọn toàn thị trường hoặc từng thị trường:",chatId,signalKeyboard());
  else if(cb==="prop")await sendText(env,"🏦 PROP\n\nTheo dõi các tài khoản quỹ được tích hợp. Kết nối execution sẽ được bật riêng cho từng quỹ sau khi xác nhận API/rule.",chatId,propKeyboard());
  else if(cb==="prop:hyro")await sendText(env,"🟣 HYROTRADER\n\nTrạng thái: CHƯA KẾT NỐI TÀI KHOẢN/API.\nSignal engine vẫn hoạt động độc lập; chưa tự gửi lệnh vào quỹ.",chatId,propKeyboard());
  else if(cb==="prop:breakout")await sendText(env,"🔵 BREAKOUT\n\nTrạng thái: CHƯA KẾT NỐI TÀI KHOẢN/API.\nChưa bật auto-execution cho tới khi quyền bot/API được xác nhận.",chatId,propKeyboard());
  else if(cb==="prop:orders"||cb==="prop:risk")await sendText(env,"🏦 PROP\n\nChưa có tài khoản prop được kết nối nên chưa có position/risk telemetry riêng.",chatId,propKeyboard());
  else if(cb==="personal")await sendText(env,"👤 CÁ NHÂN\n\nTheo dõi tài khoản cá nhân đã tích hợp. MT5 Bridge sẽ cung cấp equity, positions, broker bid/ask và execution khi được kết nối.",chatId,personalKeyboard());
  else if(cb?.startsWith("personal:"))await sendText(env,"👤 MT5 CÁ NHÂN\n\nTrạng thái: CHƯA KẾT NỐI MT5 BRIDGE.\nKhi kết nối, khu vực này sẽ hiển thị Equity • Daily P/L • Live Positions • Pending • Risk.",chatId,personalKeyboard());
  else if(cb==="hub"||text==="/hub")await sendHub(env,chatId);
  else if(cb==="symbols")await sendText(env,"🔎 Chọn thị trường để tìm từng symbol:",chatId,symbolMarketKeyboard());
  else if(cb?.startsWith("symmarket:")){const g=cb.split(":")[1];await sendText(env,"🔎 "+groupTitle(g)+" • chọn symbol",chatId,symbolPageKeyboard(g,0));}
  else if(cb?.startsWith("sympage:")){const [,g,p]=cb.split(":");await sendText(env,"🔎 "+groupTitle(g)+" • chọn symbol",chatId,symbolPageKeyboard(g,Number(p)));}
  else if(cb?.startsWith("sym:")){const [,g,raw]=cb.split(":");let symbol=canonicalUserSymbol(raw);await sendText(env,"⏳ Quét MỚI "+symbol+"...",chatId);const a=await runSymbol(symbol,env),books=await getBooks(env),added=fillBooks(g,books,[a],"SYMBOL_MANUAL");if(added.length)await saveBooks(env,books);let msg=singleAnalysisText(a);if(added.length)msg+="\n\n✅ Đã ghi lệnh vào LIVE ORDERS • nguồn SYMBOL MANUAL";await sendText(env,msg,chatId,symbolPageKeyboard(g,Math.floor(Math.max(0,symbolListFor(g).indexOf(symbol))/12)));}
  else if(cb==="noop"){}
  else if(cb?.startsWith("scan:"))await sendGroup(cb.split(":")[1],env,chatId);
  else if(cb?.startsWith("news:")){
    const [,group,symbol]=cb.split(":");if(GROUPS[group]?.includes(norm(symbol))){
      await setNewsClearance(symbol,env);await sendText(env,`✅ Tin/context OK cho ${norm(symbol)} trong ${Math.round(CONFIG.newsClearanceTtlSec/60)} phút. Đang kiểm tra lại...`,chatId);
      const a=await runSymbol(symbol,env);
      const books=await getBooks(env);fillBooks(group,books,[a],"NEWS_MANUAL");await saveBooks(env,books);await sendText(env,summary(group,books,{requested:1,broadOk:1,deepRequested:1,deepOk:a.ok===false?0:1,newCount:["MARKET","LIMIT","MARKET_SIGNAL"].includes(a.status)?1:0,analyses:[a]}),chatId,groupKeyboard(group,{analyses:[a]}));
    }
  }else {
    const cm=text.trim().match(/^\/(?:coin|analyze|forex|metal|future)\s+([A-Za-z0-9]+)$/i);
    if(cm){
      let symbol=canonicalUserSymbol(cm[1]);if(!symbol.endsWith("USDT")&&CRYPTO_BASE.includes(symbol))symbol=symbol+"USDT";
      await sendText(env,`⏳ Đang phân tích ${symbol} theo profile riêng...`,chatId);
      const a=await runSymbol(symbol,env),type=marketType(symbol);
      if(type!=="unknown"){const books=await getBooks(env);const added=fillBooks(type,books,[a],"COMMAND_MANUAL");if(added.length||a.status==="WATCH")await saveBooks(env,books);}
      await sendText(env,singleAnalysisText(a),chatId,baseKeyboard());
    }else if(cb==="books"||cb==="live")await sendText(env,"📚 LIVE CENTER\n\nLive đã tách riêng theo từng thị trường trong Hub mới.",chatId,baseKeyboard());
    else if(cb==="status"||text==="/status")await sendText(env,`⚙️ SYSTEM STATUS\nVersion: ${CONFIG.version}\nKV: ${env.TRADING_STATE?"ONLINE":"MISSING"}\nTwelve Data: ${env.TWELVE_DATA_API_KEY?"CONFIGURED":"MISSING"}\nTelegram: CONNECTED\nHub: ADAPTIVE + FRESH SCAN\nCrypto: 61 symbol\nForex: 28 pairs\nMetal: XAU/XAG\nIndex Cash: NAS100/US30/US500/DEX/JP225\nMARKET/LIMIT EXEC chỉ khi execution authority thật; MARKET PLAN/LIMIT PLAN luôn tách rõ.\nNews gate: ${env.NEWS_GATE_URL?"EXTERNAL STRICT":"SOFT UNVERIFIED"}`,chatId,baseKeyboard());
    else await sendText(env,`🤖 TRADING HUB ${CONFIG.version}\nChọn HUB/thị trường hoặc gõ /coin BTC để phân tích riêng.`,chatId,baseKeyboard());
  }
  return json({ok:true});
}

export default {
  async fetch(req,env){
    try{
      const u=new URL(req.url),p=u.pathname.replace(/\/$/,"")||"/";
      if(p==="/status")return json({ok:true,version:CONFIG.version,service:CONFIG.service,kv:!!env.TRADING_STATE,twelveData:!!env.TWELVE_DATA_API_KEY,massive:!!env.MASSIVE_API_KEY,telegram:!!env.TELEGRAM_BOT_TOKEN,v73:{version:V73_CONFIG.version,classification:V73_CONFIG.classification},providers:{forex:"Twelve Data analysis; MT5 broker quote required for execution",crypto:"Exchange-native analysis + exact canonical bid/ask execution",metal:"Twelve Data analysis; MT5 broker quote required for execution",index:"Verified native Index only: Massive I:ticker primary + Twelve Data type=Index fallback; sanity fail-closed"},newsGate:{mode:env.NEWS_GATE_URL?"EXTERNAL_STRICT":"SOFT_UNVERIFIED",clearanceTtlSec:CONFIG.newsClearanceTtlSec,externalUrlConfigured:!!env.NEWS_GATE_URL},hub:{enabled:true,freshScan:true,order:["crypto","forex","metal","index"]}});
      if(p==="/run-now"){const g=u.searchParams.get("group");return json(await runGroup(g,env,"API_RUN_NOW"));}
      if(p==="/analyze"){const symbol=u.searchParams.get("symbol");return json(await runSymbol(symbol,env));}
      if(p==="/symbols"){const g=u.searchParams.get("group");if(!GROUPS[g])return json({ok:false,error:"invalid group"},400);return json({ok:true,group:g,symbols:GROUPS[g]});}
      if(p==="/hub")return json(await runHub(env,"API_HUB"));
      if(p==="/telegram/setup-webhook")return json(await setupWebhook(req,env));
      if(p==="/telegram/webhook-info")return json(await telegram(env,"getWebhookInfo",{}));
      if(p==="/telegram/menu"){await sendText(env,`🤖 TRADING HUB ${CONFIG.version}\nMỗi lần bấm = quét mới. Chọn HUB/thị trường hoặc 🔎 TỪNG SYMBOL.`,env.TELEGRAM_CHAT_ID,baseKeyboard());return json({ok:true});}
      if(p==="/telegram/webhook"&&req.method==="POST")return handleTelegram(req,env);
      if(p==="/books"||p==="/orders"){const g=u.searchParams.get("group");if(g&&!GROUPS[g])return json({ok:false,error:"invalid group"},400);return json(await getBooksLive(env,g||null));}
      if(p==="/order-history"||p==="/history")return json(await getOrderHistory(env));
      if(p==="/knowledge"){const symbol=canonicalUserSymbol(u.searchParams.get("symbol"));return json({ok:true,symbol,knowledge:symbolKnowledge(symbol)});}
      if(p==="/shadow"){const symbol=u.searchParams.get("symbol");return json({ok:true,rows:await getShadowSetups(env,symbol)});}
      if(p==="/latest-scan"){const g=u.searchParams.get("group");if(!GROUPS[g])return json({ok:false,error:"invalid group"},400);return json({ok:true,group:g,snapshot:await getScanSnapshot(g,env)});}
      return json({ok:true,version:CONFIG.version,endpoints:["/status","/hub","/run-now?group=forex|crypto|metal|index","/analyze?symbol=BTCUSDT|EURUSD|XAUUSD|NAS100|US30|US500|DEX|JP225","/symbols?group=forex|crypto|metal|index","/knowledge?symbol=NAS100","/telegram/menu","/books","/order-history"]});
    }catch(e){console.error("HTTP",e);return json({ok:false,version:CONFIG.version,error:e?.message||String(e)},500);}
  },
  async scheduled(_controller,env,ctx){ctx.waitUntil((async()=>{await lifecycle(env);const t=new Date(Number(_controller?.scheduledTime||Date.now())),minute=t.getUTCMinutes();if(minute%CONFIG.autoCryptoScanMinutes===0)await autoScanCrypto(env);if(minute===2)await autoScanSignalGroup("forex",env);if(minute===12)await autoScanSignalGroup("metal",env);if(minute%15===7)await autoScanSignalGroup("index",env);})().catch(e=>console.error("CRON",e)));}
};
