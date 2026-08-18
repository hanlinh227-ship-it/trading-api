const fs = require('fs');
const path = 'cloudflare-worker/index.js';
let s = fs.readFileSync(path, 'utf8');

function replaceRange(startMarker, endMarker, replacement, label) {
  const a = s.indexOf(startMarker);
  if (a < 0) throw new Error(`Missing start marker ${label}: ${startMarker}`);
  const b = s.indexOf(endMarker, a);
  if (b < 0) throw new Error(`Missing end marker ${label}: ${endMarker}`);
  s = s.slice(0, a) + replacement + s.slice(b);
}
function mustReplace(from, to, label) {
  if (!s.includes(from)) throw new Error(`Missing replace target ${label}`);
  s = s.replace(from, to);
}

s = s.replaceAll('V77.7.1', 'V77.8.0');
mustReplace(
  'function tdFullScanCost(group){return group==="forex"?43:group==="crypto"?45:group==="metal"?12:0;}',
  'function tdFullScanCost(group){return group==="forex"?43:group==="crypto"?0:group==="metal"?12:0;}',
  'Twelve Data scan cost'
);

const cryptoNative = String.raw`
const CRYPTO_TF = ["5min","15min","1h","4h","1day"];
function cryptoTfSec(interval){return {"5min":300,"15min":900,"1h":3600,"4h":14400,"1day":86400}[interval]||0;}
function bybitInterval(interval){return {"5min":"5","15min":"15","1h":"60","4h":"240","1day":"D"}[interval];}
function okxInterval(interval){return {"5min":"5m","15min":"15m","1h":"1H","4h":"4H","1day":"1Dutc"}[interval];}
function binanceInterval(interval){return {"5min":"5m","15min":"15m","1h":"1h","4h":"4h","1day":"1d"}[interval];}
function normalizeExchangeCandles(rows,sec){
  const t=nowSec();
  return (rows||[]).map(r=>({timestamp:Number(r.timestamp),open:Number(r.open),high:Number(r.high),low:Number(r.low),close:Number(r.close),volume:num(r.volume)}))
    .filter(c=>c.timestamp&&Number.isFinite(c.close)&&c.timestamp+sec<=t)
    .sort((a,b)=>a.timestamp-b.timestamp);
}
async function bybitCandles(symbol,interval,limit=CONFIG.candleOutputSize){
  const p=await bybit("/v5/market/kline",{category:"spot",symbol:norm(symbol),interval:bybitInterval(interval),limit:String(limit)});
  const sec=cryptoTfSec(interval);
  return normalizeExchangeCandles((p?.result?.list||[]).map(r=>({timestamp:Math.floor(Number(r[0])/1000),open:r[1],high:r[2],low:r[3],close:r[4],volume:r[5]})),sec);
}
async function okxCandles(symbol,interval,limit=CONFIG.candleOutputSize){
  const p=await okx("/api/v5/market/candles",{instId:okxId(symbol),bar:okxInterval(interval),limit:String(Math.min(limit,300))});
  const sec=cryptoTfSec(interval);
  return normalizeExchangeCandles((p?.data||[]).filter(r=>String(r[8]??"1")==="1").map(r=>({timestamp:Math.floor(Number(r[0])/1000),open:r[1],high:r[2],low:r[3],close:r[4],volume:r[5]})),sec);
}
async function binanceCandles(symbol,interval,limit=CONFIG.candleOutputSize){
  const s0=norm(symbol),iv=binanceInterval(interval);let last=null;
  for(const host of ["https://data-api.binance.vision","https://api.binance.com"]){
    try{
      const r=await fetchTimeout(`${host}/api/v3/klines?symbol=${encodeURIComponent(s0)}&interval=${iv}&limit=${Math.min(limit,1000)}`);
      const p=await r.json();if(!r.ok||!Array.isArray(p))throw new Error(p?.msg||`Binance ${r.status}`);
      const sec=cryptoTfSec(interval);
      return normalizeExchangeCandles(p.map(x=>({timestamp:Math.floor(Number(x[0])/1000),open:x[1],high:x[2],low:x[3],close:x[4],volume:x[5]})),sec);
    }catch(e){last=e;}
  }
  throw last||new Error("Binance candles unavailable");
}
async function cryptoDeepBundle(symbol){
  const s0=norm(symbol),venues=[
    {name:"Bybit Spot",quote:bybitQuote,candles:bybitCandles},
    {name:"OKX Spot",quote:okxQuote,candles:okxCandles},
    {name:"Binance Spot",quote:binanceQuote,candles:binanceCandles},
  ],errors=[];
  for(const v of venues){
    try{
      const [quote,...candles]=await Promise.all([v.quote(s0),...CRYPTO_TF.map(tf0=>v.candles(s0,tf0))]);
      if(candles.some(c=>!Array.isArray(c)||c.length<55))throw new Error("insufficient closed candles");
      return {source:v.name,quote,candles};
    }catch(e){errors.push(`${v.name}: ${e?.message||String(e)}`);}
  }
  throw new Error(`No exact exchange deep bundle: ${errors.join(" | ")}`);
}
`;

const emaMarker = 'function ema(values,n){';
const emaPos = s.indexOf(emaMarker);
if (emaPos < 0) throw new Error('Missing EMA marker');
s = s.slice(0, emaPos) + cryptoNative + '\n' + s.slice(emaPos);

const deepReplacement = String.raw`
function buildTradePlan(side,entry,M5,M15,H1,trig,pendingRetest){
  const atrFloor=M5.atr14*.8;
  const structure=side==="LONG"
    ?Math.min(M5.liquidityLow20??entry-atrFloor,M15.liquidityLow20??entry-atrFloor)
    :Math.max(M5.liquidityHigh20??entry+atrFloor,M15.liquidityHigh20??entry+atrFloor);
  const sl=side==="LONG"?Math.min(structure,entry-atrFloor):Math.max(structure,entry+atrFloor);
  const risk=Math.abs(entry-sl);if(!Number.isFinite(risk)||risk<=0)return null;
  const opp=side==="LONG"?H1.liquidityHigh20:H1.liquidityLow20;
  const roomR=opp===null?null:Math.abs(opp-entry)/risk;
  if(roomR===null||roomR<CONFIG.minRoomR)return {invalid:"H1_CLEAN_ROOM_REQUIRED",roomR,risk,sl};
  const targetRR=roomR>=CONFIG.rr2RoomRequired?2:1;
  return {entry,sl,risk,roomR,targetRR,tp1:side==="LONG"?entry+risk:entry-risk,tp2:side==="LONG"?entry+risk*2:entry-risk*2,mode:pendingRetest?"LIMIT":"MARKET",triggerLevel:trig?.level??null};
}
async function deepAnalyze(symbol,env,preparedCandles=null,preparedReference=null,preparedSource=null){
  const s0=norm(symbol),type=marketType(s0);
  if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s0,reason:"UNSUPPORTED_SYMBOL"};
  const prior=v73Prior(s0,type);
  let candles=preparedCandles;
  try{
    if(!candles){
      if(type==="crypto"){const b=await cryptoDeepBundle(s0);candles=b.candles;preparedReference=b.quote;preparedSource=b.source;}
      else candles=await Promise.all(["5min","15min","1h","4h","1day"].map(i=>tdCandles(s0,i,env)));
    }
  }catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s0,reason:"ANALYSIS_DATA_UNAVAILABLE",error:e?.message||String(e)};}
  if(!Array.isArray(candles)||candles.length!==5)return watch(s0,type,"NEUTRAL","TIMEFRAME_DATA_REQUIRED",{canonical:{v73Prior:prior}});
  const [m5c,m15c,h1c,h4c,d1c]=candles,[M5,M15,H1,H4,D1]=candles.map(tf);
  if([M5,M15,H1,H4,D1].some(x=>!x?.ready))return watch(s0,type,"NEUTRAL","TIMEFRAME_DATA_REQUIRED",{canonical:{v73Prior:prior},source:preparedSource});
  const long=D1.trend==="BULLISH"&&H4.trend==="BULLISH"&&H1.trend==="BULLISH";
  const short=D1.trend==="BEARISH"&&H4.trend==="BEARISH"&&H1.trend==="BEARISH";
  if(!long&&!short)return watch(s0,type,"NEUTRAL","HTF_ALIGNMENT_REQUIRED",{canonical:{v73Prior:prior},source:preparedSource});
  const side=long?"LONG":"SHORT",loc=m15Location(m15c,M15,side);
  if(!loc.valid)return watch(s0,type,side,"M15_LOCATION_REQUIRED",{canonical:{v73Prior:prior,m15Location:loc},source:preparedSource});
  const trig=m5Trigger(m5c,M5,side);
  const pendingRetest=!trig.valid&&trig.mss===true&&trig.displacement===true&&trig.retest===false&&Number.isFinite(trig.level);
  if(!trig.valid&&!pendingRetest)return watch(s0,type,side,"M5_MSS_DISPLACEMENT_RETEST_REQUIRED",{canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig},source:preparedSource});
  if(!M5.atr14)return watch(s0,type,side,"ATR_REQUIRED",{source:preparedSource});
  const previewEntry=pendingRetest?Number(trig.level):M5.close,preview=buildTradePlan(side,previewEntry,M5,M15,H1,trig,pendingRetest);
  if(!preview)return watch(s0,type,side,"STRUCTURAL_SL_REQUIRED",{source:preparedSource});
  if(preview.invalid)return watch(s0,type,side,preview.invalid,{roomR:preview.roomR,source:preparedSource});
  const planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,roomR:preview.roomR,mode:preview.mode,reference:type==="crypto"?(preparedSource||"Exact exchange"):"Closed M5 analysis"};
  const news=await getNewsClearance(s0,env);
  if(!news)return watch(s0,type,side,"NEWS_CONTEXT_REQUIRED",{setupReady:true,planned,source:preparedSource,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:false}}});
  if(type!=="crypto")return watch(s0,type,side,"EXECUTION_QUOTE_REQUIRED",{setupReady:true,planned,currentPrice:M5.close,source:"Twelve Data analysis",canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true}}});
  let reference=preparedReference;
  try{if(!reference)reference=await cryptoExecutionQuote(s0);}catch(e){return watch(s0,type,side,"FINAL_QUOTE_REQUIRED",{setupReady:true,planned,error:e?.message||String(e)});}
  if(!reference.fresh)return watch(s0,type,side,"FINAL_QUOTE_STALE",{setupReady:true,planned,quote:reference});
  if(!reference.executionVerified)return watch(s0,type,side,"EXECUTION_QUOTE_REQUIRED",{setupReady:true,planned,quote:reference});
  const finalEntry=pendingRetest?Number(trig.level):reference.price,plan=buildTradePlan(side,finalEntry,M5,M15,H1,trig,pendingRetest);
  if(!plan||plan.invalid)return watch(s0,type,side,plan?.invalid||"STRUCTURAL_SL_REQUIRED",{setupReady:true,planned,quote:reference});
  const spread=reference.ask-reference.bid,costR=spread/plan.risk;
  if(!Number.isFinite(costR)||costR>CONFIG.maxExecutionCostR)return watch(s0,type,side,"EXECUTION_COST_TOO_HIGH",{setupReady:true,planned,costR,roomR:plan.roomR,quote:reference});
  return {ok:true,status:plan.mode,action:plan.mode,symbol:s0,market:type,side,entry:plan.entry,currentPrice:reference.price,sl:plan.sl,tp1:plan.tp1,tp2:plan.tp2,targetRR:plan.targetRR,roomR:plan.roomR,risk:{riskUsd:CONFIG.defaultRiskUsd,distance:plan.risk,quantity:CONFIG.defaultRiskUsd/plan.risk},quote:reference,source:preparedSource||reference.source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true},execution:{verified:true,spread,costR}},engine:CONFIG.version};
}
`;
replaceRange('async function deepAnalyze(', '\nfunction broadRank(', deepReplacement + '\nfunction broadRank(', 'deepAnalyze');

const broadReplacement = String.raw`
async function broadScan(group,env){
  const symbols=GROUPS[group],rows=[],errors=[];
  if(group==="crypto"){
    const bulk=await cryptoBulk().catch(()=>new Map());
    for(const sym of symbols){
      const q=bulk.get(sym);
      if(q?.price)rows.push({symbol:sym,quote:q,strength:broadRank(q)});
      else errors.push({symbol:sym,reason:"EXACT_SPOT_UNAVAILABLE"});
    }
  }else{
    let map=new Map();
    try{map=await tdBatchCandles(symbols,"1h",env,60);}
    catch(e){for(const sym of symbols)errors.push({symbol:sym,reason:"H1_BATCH_UNAVAILABLE",error:e?.message||String(e)});return {requested:symbols.length,rows,errors};}
    for(const sym of symbols){
      const c=map.get(sym),T=tf(c||[]);
      if(!T.ready){errors.push({symbol:sym,reason:"H1_UNAVAILABLE"});continue;}
      rows.push({symbol:sym,quote:{source:"Twelve Data H1",price:T.close,fresh:true},strength:Math.abs((T.close-(T.ema20??T.close))/(T.atr14||1))});
    }
  }
  rows.sort((a,b)=>b.strength-a.strength);
  return {requested:symbols.length,rows,errors};
}
`;
replaceRange('async function broadScan(', '\nfunction emptyGroup(', broadReplacement + '\nfunction emptyGroup(', 'broadScan');

mustReplace(
  'const watches=analyses.filter(x=>x.status==="WATCH").sort((a,b)=>Number(b.setupReady)-Number(a.setupReady)).slice(0,CONFIG.maxWatch).map(x=>({symbol:x.symbol,side:x.side,reason:x.reason,canonicalStage:x.canonicalStage,updatedAt:Date.now(),engine:CONFIG.version})); b.watch=watches; return newItems;',
  'const watches=analyses.filter(x=>x.status==="WATCH").sort((a,b)=>Number(b.setupReady)-Number(a.setupReady)).slice(0,CONFIG.maxWatch).map(x=>({symbol:x.symbol,side:x.side,reason:x.reason,canonicalStage:x.canonicalStage,setupReady:!!x.setupReady,planned:x.planned||null,source:x.source||null,updatedAt:Date.now(),engine:CONFIG.version})); b.watch=watches; return newItems;',
  'watch persistence'
);

const runReplacement = String.raw`
async function runGroup(group,env){
  if(!GROUPS[group])throw new Error("invalid group");
  if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group};
  const started=Date.now();
  try{
    const budget=await ensureTdBudget(group,env);
    if(!budget.ok){
      const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};
      await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;
    }
    const broad=await broadScan(group,env),candidates=broad.rows.slice(0,CONFIG.maxCandidates),analyses=[];
    if(group==="crypto"){
      const bundles=await Promise.all(candidates.map(async c=>{try{return [c.symbol,await cryptoDeepBundle(c.symbol)];}catch(e){return [c.symbol,{error:e?.message||String(e)}];}}));
      const map=new Map(bundles);
      for(const c of candidates){
        if(Date.now()-started>CONFIG.scanDeadlineMs)break;
        const b=map.get(c.symbol);
        if(!b||b.error)analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"EXCHANGE_DEEP_UNAVAILABLE",error:b?.error||"missing bundle"});
        else analyses.push(await deepAnalyze(c.symbol,env,b.candles,b.quote,b.source));
      }
    }else{
      let prepared=new Map();try{prepared=await prepareDeepCandles(candidates.map(c=>c.symbol),env);}catch{}
      for(const c of candidates){
        if(Date.now()-started>CONFIG.scanDeadlineMs)break;
        const pc=prepared.get(c.symbol);
        if(!pc)analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"ANALYSIS_DATA_UNAVAILABLE"});
        else analyses.push(await deepAnalyze(c.symbol,env,pc,null,"Twelve Data"));
      }
    }
    const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);
    const out={ok:true,version:CONFIG.version,group,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:candidates.length,deepOk:analyses.filter(a=>a.ok!==false).length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};
    await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;
  }finally{await releaseLock(env);}
}
`;
replaceRange('async function runGroup(', '\nasync function telegram(', runReplacement + '\nasync function telegram(', 'runGroup');

const uiReplacement = String.raw`
function keyboard(group=null,books=null){
  const rows=[
    [{text:"🧭 HUB TOP SETUPS",callback_data:"hub"}],
    [{text:"💱 FOREX",callback_data:"scan:forex"},{text:"🪙 CRYPTO",callback_data:"scan:crypto"},{text:"🥇 METAL",callback_data:"scan:metal"}],
    [{text:"📊 STATUS",callback_data:"status"},{text:"📚 BOOKS",callback_data:"books"}]
  ];
  if(group&&books){
    const pending=(books?.[group]?.watch||[]).filter(w=>w.reason==="NEWS_CONTEXT_REQUIRED").slice(0,3);
    if(pending.length)rows.unshift(pending.map(w=>({text:`✅ Tin OK ${w.symbol}`,callback_data:`news:${group}:${w.symbol}`})));
  }
  return {inline_keyboard:rows};
}
function groupTitle(g){return g==="forex"?"💱 FOREX":g==="crypto"?"🪙 CRYPTO":"🥇 METAL";}
function fmtPx(v){const n=Number(v);return Number.isFinite(n)?n.toPrecision(7):"?";}
function posLine(p){return `${p.symbol} ${sideText(p.side)} | E ${fmtPx(p.entry)} | SL ${fmtPx(p.sl)} | TP ${fmtPx(p.tp)}`;}
function watchLine(w){
  let x=`${w.symbol} ${sideText(w.side)} | ${w.reason||"CHỜ XÁC NHẬN"}`;
  if(w.planned)x+=` | E~${fmtPx(w.planned.entry)} SL~${fmtPx(w.planned.sl)} TP~${fmtPx(w.planned.targetRR===2?w.planned.tp2:w.planned.tp1)}`;
  return x;
}
function summary(group,books,run=null){
  const b=books[group],L=[groupTitle(group),"",`🟢 MARKET ${b.marketActive.length}/${CONFIG.maxMarketActive}`];
  if(b.marketActive.length)b.marketActive.forEach((p,i)=>L.push(`${i+1}. ${posLine(p)}`));else L.push("Trống");
  L.push("",`🔵 LIMIT ĐÃ KHỚP ${b.limitActive.length}/${CONFIG.maxLimitActive}`);
  if(b.limitActive.length)b.limitActive.forEach((p,i)=>L.push(`${i+1}. ${posLine(p)}`));else L.push("Trống");
  L.push("",`🟡 LIMIT CHỜ ${b.limitPending.length}/${CONFIG.maxPendingLimit}`);
  if(b.limitPending.length)b.limitPending.forEach((p,i)=>L.push(`${i+1}. ${posLine(p)}`));else L.push("Trống");
  L.push("",`👀 WATCH ${b.watch.length}/${CONFIG.maxWatch}`);
  if(b.watch.length)b.watch.forEach((w,i)=>L.push(`${i+1}. ${watchLine(w)}`));else L.push("Trống");
  if(run){
    if(run.status==="RATE_BUDGET_WAIT"){L.push(`⏱ Twelve Data còn ${run.diagnostics?.tdCreditsLeft??"?"} credit; cần ${run.diagnostics?.tdCreditsRequired??"?"}. Thử lại sau ~${run.retryAfterSec??60}s.`);return L.join("\\n");}
    L.push(`🔍 Quét: ${run.requested} | Deep OK: ${run.deepOk}/${run.deepRequested} | Mới: ${run.newCount}`);
    L.push(`🧪 Coverage: ${run.broadOk}/${run.requested}`);
    const rs=run.analyses.map(a=>`${a.symbol}=${a.status}${a.reason?`(${a.reason})`:""}`).join(" | ");if(rs)L.push(`📍 ${rs}`);
  }
  return L.join("\\n");
}
async function sendGroup(group,env,chatId){
  await sendText(env,`⏳ Đang quét ${group.toUpperCase()}...`,chatId);
  const run=await runGroup(group,env),books=await getBooks(env);
  return sendText(env,summary(group,books,run),chatId,keyboard(group,books));
}
function hubRank(a){
  if(a.status==="MARKET")return 100;
  if(a.status==="LIMIT")return 95;
  if(a.reason==="NEWS_CONTEXT_REQUIRED")return 85;
  if(a.reason==="EXECUTION_QUOTE_REQUIRED")return 80;
  if(a.reason==="FINAL_QUOTE_REQUIRED")return 75;
  if(a.reason==="EXECUTION_COST_TOO_HIGH")return 70;
  if(a.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")return 55;
  if(a.reason==="M15_LOCATION_REQUIRED")return 40;
  if(a.reason==="HTF_ALIGNMENT_REQUIRED")return 20;
  return 10;
}
async function runHub(env){
  const runs={};
  for(const g of ["crypto","forex","metal"])runs[g]=await runGroup(g,env);
  const items=Object.entries(runs).flatMap(([group,r])=>(r.analyses||[]).map(a=>({...a,group}))).sort((a,b)=>hubRank(b)-hubRank(a)).slice(0,7);
  return {ok:true,version:CONFIG.version,runs,top:items};
}
function hubSummary(h){
  const L=[`🧭 TRADING HUB ${CONFIG.version}`,"","Top setup hiện tại:"];
  if(!h.top.length)L.push("Chưa có setup đủ tốt.");
  h.top.forEach((a,i)=>{
    let line=`${i+1}. ${a.symbol} ${sideText(a.side)} | ${a.status}${a.reason?` • ${a.reason}`:""}`;
    if(a.planned)line+=` | E~${fmtPx(a.planned.entry)} SL~${fmtPx(a.planned.sl)} TP~${fmtPx(a.planned.targetRR===2?a.planned.tp2:a.planned.tp1)}`;
    if(a.quote?.source||a.source)line+=` | ${a.quote?.source||a.source}`;
    L.push(line);
  });
  L.push("","MARKET/LIMIT chỉ xuất hiện khi mọi canonical gate + execution quote đều PASS.");
  for(const g of ["forex","crypto","metal"]){const r=h.runs[g];L.push(`${groupTitle(g)}: ${r.status==="RATE_BUDGET_WAIT"?"đợi quota":`${r.broadOk}/${r.requested} coverage, deep ${r.deepOk}/${r.deepRequested}`}`);}
  return L.join("\\n");
}
async function sendHub(env,chatId){
  await sendText(env,"⏳ HUB đang quét Crypto + Forex + Metal...",chatId);
  const h=await runHub(env);return sendText(env,hubSummary(h),chatId,keyboard());
}
function booksSummary(books){
  const L=["📚 BOOKS"];
  for(const g of ["forex","crypto","metal"]){const b=books[g];L.push(`${groupTitle(g)} • M ${b.marketActive.length} • L ${b.limitActive.length} • Pending ${b.limitPending.length} • Watch ${b.watch.length}`);}
  return L.join("\\n");
}
`;
replaceRange('function keyboard(', '\nasync function lifecycle(', uiReplacement + '\nasync function lifecycle(', 'Telegram UI');

const lifecycleReplacement = String.raw`
async function lifecycle(env){
  const books=await getBooks(env);let changed=false;
  const b=books.crypto;
  const pending=[];
  for(const p of b.limitPending){
    if(p.expiresAt&&Date.now()>p.expiresAt){changed=true;continue;}
    try{
      const q=await cryptoExecutionQuote(p.symbol),px=q.price,fill=p.side==="LONG"?px<=p.entry:px>=p.entry;
      if(fill&&b.limitActive.length<CONFIG.maxLimitActive){p.status="ACTIVE";p.openedAt=Date.now();b.limitActive.push(p);changed=true;await sendText(env,`🔵 LIMIT ĐÃ KHỚP\\n${p.symbol} ${sideText(p.side)}\\nEntry: ${p.entry}`).catch(()=>{});}else pending.push(p);
    }catch{pending.push(p);}
  }
  b.limitPending=pending;
  for(const key of ["marketActive","limitActive"]){
    const keep=[];
    for(const p of b[key]){
      try{
        const q=await cryptoExecutionQuote(p.symbol),px=q.price,hitTP=p.side==="LONG"?px>=p.tp:px<=p.tp,hitSL=p.side==="LONG"?px<=p.sl:px>=p.sl;
        if(hitTP||hitSL){changed=true;await sendText(env,`${hitTP?"✅ TAKE PROFIT":"❌ STOP LOSS"}\\n${p.symbol} ${sideText(p.side)}\\n${hitTP?"TP":"SL"}: ${px}`).catch(()=>{});}else keep.push(p);
      }catch{keep.push(p);}
    }
    b[key]=keep;
  }
  if(changed)await saveBooks(env,books);
}
`;
replaceRange('async function lifecycle(', '\nasync function setupWebhook(', lifecycleReplacement + '\nasync function setupWebhook(', 'lifecycle');

const telegramReplacement = String.raw`
async function handleTelegram(req,env){
  if(!verifyTelegram(req,env))return json({ok:false,error:"invalid telegram secret"},403);
  const u=await req.json(),chatId=u?.callback_query?.message?.chat?.id??u?.message?.chat?.id??env.TELEGRAM_CHAT_ID,cb=u?.callback_query?.data,text=String(u?.message?.text||"");
  if(u?.callback_query?.id)telegram(env,"answerCallbackQuery",{callback_query_id:u.callback_query.id}).catch(()=>{});
  if(cb==="hub"||text==="/hub")await sendHub(env,chatId);
  else if(cb?.startsWith("scan:"))await sendGroup(cb.split(":")[1],env,chatId);
  else if(cb?.startsWith("news:")){
    const [,group,symbol]=cb.split(":");
    if(GROUPS[group]?.includes(norm(symbol))){
      await setNewsClearance(symbol,env);
      await sendText(env,`✅ Tin/context OK cho ${norm(symbol)} trong ${Math.round(CONFIG.newsClearanceTtlSec/60)} phút. Đang kiểm tra lại...`,chatId);
      let analysis;
      if(group==="crypto"){try{const b=await cryptoDeepBundle(symbol);analysis=await deepAnalyze(symbol,env,b.candles,b.quote,b.source);}catch(e){analysis={ok:false,status:"DATA_BLOCK",symbol:norm(symbol),reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)};}}
      else analysis=await deepAnalyze(symbol,env);
      const books=await getBooks(env);fillBooks(group,books,[analysis]);await saveBooks(env,books);
      await sendText(env,summary(group,books,{requested:1,broadOk:1,deepRequested:1,deepOk:analysis.ok===false?0:1,newCount:["MARKET","LIMIT"].includes(analysis.status)?1:0,analyses:[analysis]}),chatId,keyboard(group,books));
    }
  }else if(cb==="books"){await sendText(env,booksSummary(await getBooks(env)),chatId,keyboard());}
  else if(cb==="status"||text==="/status")await sendText(env,`⚙️ SYSTEM STATUS\nVersion: ${CONFIG.version}\nKV: ${env.TRADING_STATE?"ONLINE":"MISSING"}\nTwelve Data: ${env.TWELVE_DATA_API_KEY?"CONFIGURED":"MISSING"}\nTelegram: CONNECTED\nHub: UNIFIED\nCrypto deep: exact exchange-native 5TF + bid/ask\nForex/Metal: Twelve Data analysis; broker execution quote required\nNews gate: STRICT\nV73: FROZEN PRIOR\nV76 R2: RESEARCH ONLY`,chatId,keyboard());
  else await sendText(env,`🤖 TRADING HUB ${CONFIG.version}\\nChọn HUB hoặc thị trường:`,chatId,keyboard());
  return json({ok:true});
}
`;
replaceRange('async function handleTelegram(', '\nexport default {', telegramReplacement + '\nexport default {', 'handleTelegram');

mustReplace(
  'crypto:"Twelve Data batch analysis + Binance/Bybit/OKX execution"',
  'crypto:"Exact exchange-native 5TF analysis + Binance/Bybit/OKX execution"',
  'status crypto provider'
);
mustReplace(
  'endpoints:["/status","/run-now?group=forex|crypto|metal","/telegram/setup-webhook","/telegram/webhook-info","/telegram/menu","/books"]',
  'endpoints:["/status","/hub","/run-now?group=forex|crypto|metal","/telegram/setup-webhook","/telegram/webhook-info","/telegram/menu","/books"]',
  'endpoint list'
);
mustReplace(
  'if(p==="/run-now"){const g=u.searchParams.get("group");return json(await runGroup(g,env));}',
  'if(p==="/run-now"){const g=u.searchParams.get("group");return json(await runGroup(g,env));}\\n      if(p==="/hub")return json(await runHub(env));',
  'hub endpoint'
);

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.8.0 unified Telegram Hub + exchange-native Crypto deep engine.');
