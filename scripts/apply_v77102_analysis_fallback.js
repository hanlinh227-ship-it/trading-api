const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing start '+label);const b=s.indexOf(end,a+start.length);if(b<0)throw new Error('Missing end '+label);s=s.slice(0,a)+repl+s.slice(b);}

s=s.replaceAll('V77.10.1','V77.10.2');
s=s.replaceAll('Trading V77.10.2 Adaptive Entry Intelligence Hub','Trading V77.10.2 Adaptive Entry Intelligence Hub');

const fallbackFns=[
'function kucoinId(symbol){const x=norm(symbol);if(!x.endsWith("USDT"))throw new Error("not USDT");return x.slice(0,-4)+"-USDT";}',
'function gateId(symbol){const x=norm(symbol);if(!x.endsWith("USDT"))throw new Error("not USDT");return x.slice(0,-4)+"_USDT";}',
'function kucoinInterval(i){return {"5min":"5min","15min":"15min","1h":"1hour","4h":"4hour","1day":"1day"}[i];}',
'function gateInterval(i){return {"5min":"5m","15min":"15m","1h":"1h","4h":"4h","1day":"1d"}[i];}',
'async function kucoinCandles(symbol,interval){',
'  const q=new URLSearchParams({symbol:kucoinId(symbol),type:kucoinInterval(interval)}),r=await fetchTimeout("https://api.kucoin.com/api/v1/market/candles?"+q),p=await r.json().catch(()=>null);',
'  if(!r.ok||p?.code!=="200000"||!Array.isArray(p?.data))throw new Error("KuCoin candles unavailable");',
'  return normalizeCandles(p.data.map(x=>({timestamp:Number(x[0]),open:x[1],close:x[2],high:x[3],low:x[4],volume:x[5]})),candleSec(interval));',
'}',
'async function gateCandles(symbol,interval){',
'  const q=new URLSearchParams({currency_pair:gateId(symbol),interval:gateInterval(interval),limit:String(CONFIG.candleOutputSize)}),r=await fetchTimeout("https://api.gateio.ws/api/v4/spot/candlesticks?"+q,{headers:{Accept:"application/json"}}),p=await r.json().catch(()=>null);',
'  if(!r.ok||!Array.isArray(p))throw new Error("Gate candles unavailable");',
'  return normalizeCandles(p.filter(x=>String(x[7]??"true")!=="false").map(x=>({timestamp:Number(x[0]),open:x[5],high:x[3],low:x[4],close:x[2],volume:x[6]})),candleSec(interval));',
'}',
'async function analysisOnlyQuote(symbol,preferred){',
'  const s=norm(symbol);try{const m=await cryptoBulk(),q=m.get(s);if(q?.price)return {...q,analysisOnly:true,executionVerified:false,fresh:true,source:q.source||preferred||"Broad Analysis"};}catch{}return {source:preferred||"Analysis-only",price:null,bid:null,ask:null,fresh:false,executionVerified:false,analysisOnly:true};',
'}',
'async function cryptoAnalysisFallbackBundle(symbol,preferred=null){',
'  const s=norm(symbol),venues=preferred==="gate"?[{name:"Gate Spot Analysis",candles:gateCandles},{name:"KuCoin Spot Analysis",candles:kucoinCandles}]:[{name:"KuCoin Spot Analysis",candles:kucoinCandles},{name:"Gate Spot Analysis",candles:gateCandles}],errors=[];',
'  for(const v of venues){try{const candles=await Promise.all(INTERVALS.map(i=>v.candles(s,i)));if(candles.some(c=>!Array.isArray(c)||c.length<55))throw new Error("insufficient closed candles");const quote=await analysisOnlyQuote(s,v.name);return {source:v.name,quote,candles,analysisOnly:true};}catch(e){errors.push(v.name+": "+(e?.message||String(e)));}}',
'  throw new Error("No analysis-only deep bundle: "+errors.join(" | "));',
'}',
''
].join('\n');
mustReplace('async function cryptoDeepBundle(symbol){',fallbackFns+'async function cryptoDeepBundle(symbol,options={}){','fallback function insertion');

// Replace canonical deep bundle body to support analysis-first fallback for broad-only symbols.
const deepStart='async function cryptoDeepBundle(symbol,options={}){';
const deepEnd='async function cryptoExecutionQuote(';
const deepBundle=[
'async function cryptoDeepBundle(symbol,options={}){',
'  const s=norm(symbol),preferAnalysis=!!options.preferAnalysis,canonical=[',
'    {name:"Bybit Spot",quote:bybitQuote,candles:bybitCandles},',
'    {name:"OKX Spot",quote:okxQuote,candles:okxCandles},',
'    {name:"Binance Spot",quote:binanceQuote,candles:binanceCandles},',
'  ],errors=[];',
'  if(preferAnalysis){try{return await cryptoAnalysisFallbackBundle(s,options.preferredBroadSource?.includes("Gate")?"gate":null);}catch(e){errors.push(e?.message||String(e));}}',
'  for(const v of canonical){try{const [quote,...candles]=await Promise.all([v.quote(s),...INTERVALS.map(i=>v.candles(s,i))]);if(candles.some(c=>!Array.isArray(c)||c.length<55))throw new Error("insufficient closed candles");return {source:v.name,quote,candles,analysisOnly:false};}catch(e){errors.push(v.name+": "+(e?.message||String(e)));}}',
'  if(!preferAnalysis){try{return await cryptoAnalysisFallbackBundle(s);}catch(e){errors.push(e?.message||String(e));}}',
'  throw new Error("No exact/deep analysis bundle: "+errors.join(" | "));',
'}',
''
].join('\n');
replaceRange(deepStart,deepEnd,deepBundle,'crypto deep bundle fallback');

// At final execution, analysis-only quote must be replaced by canonical executable quote.
mustReplace('try{if(!reference)reference=await cryptoExecutionQuote(s);}','try{if(!reference||reference.analysisOnly)reference=await cryptoExecutionQuote(s);}','analysis quote cannot authorize execution');

// Broad-only candidates should use analysis fallback first instead of hammering canonical venues.
mustReplace('try{b=await cryptoDeepBundle(c.symbol);}catch(e){','try{b=await cryptoDeepBundle(c.symbol,{preferAnalysis:!!c.quote?.analysisOnly,preferredBroadSource:c.quote?.source});}catch(e){','candidate preferred deep route');

// Direct symbol analysis prefers independent analysis venues first; execution remains canonical later.
mustReplace('if(type==="crypto"){let b;try{b=await cryptoDeepBundle(s);}catch(e){','if(type==="crypto"){let b;try{b=await cryptoDeepBundle(s,{preferAnalysis:true});}catch(e){','direct symbol resilient analysis');

// Direct-symbol relative context must tolerate analysis-only quote and use broad change if needed.
const oldContext='let context={score:5};try{const btc= s==="BTCUSDT"?b.quote:await cryptoExecutionQuote("BTCUSDT");const rel=(b.quote.percentChange??0)-(btc.percentChange??0);context={relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel)),...(await cryptoDerivativesContext(s))};}catch{}return deepAnalyze(s,env,b.candles,b.quote,b.source,context);';
const newContext='let context={score:5};try{const bulk=await cryptoBulk(),sq=b.quote?.percentChange??bulk.get(s)?.percentChange??0,bq=s==="BTCUSDT"?sq:(bulk.get("BTCUSDT")?.percentChange??0),rel=sq-bq;context={relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel)),...(await cryptoDerivativesContext(s))};}catch{}return deepAnalyze(s,env,b.candles,b.quote,b.source,context);';
mustReplace(oldContext,newContext,'direct context resilient');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.10.2 analysis-only deep fallback');
