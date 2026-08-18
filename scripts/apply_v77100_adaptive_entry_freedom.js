const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');

function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing start '+label);const b=s.indexOf(end,a+start.length);if(b<0)throw new Error('Missing end '+label);s=s.slice(0,a)+repl+s.slice(b);}

s=s.replaceAll('V77.9.4','V77.10.0');
s=s.replaceAll('Trading V77.9.4 Adaptive Symbol Intelligence Hub','Trading V77.10.0 Adaptive Entry Intelligence Hub');
mustReplace('  maxCandidates: 3,','  maxCandidates: 3,\n  deepShortlist: 12,\n  cryptoDeepTarget: 5,\n  cryptoDeepCooldownMs: 220,','CONFIG adaptive shortlist');

const scoreAnchor='function setupScore(parts={}){let x=0;x+=Math.min(25,(parts.methodFit||0)*.25);x+=parts.htf?20:Math.min(12,(parts.htfVotes||0)*4);x+=parts.location?15:0;x+=parts.trigger?15:parts.pending?8:0;x+=parts.plan?10:0;x+=Math.min(10,Math.max(0,parts.contextScore??5));x+=parts.news?3:0;x+=parts.execution?2:0;return Math.max(0,Math.min(100,Math.round(x)));}\n';
const adaptiveFns=[
'function profileMode(intel){',
'  const f=(intel?.families||[]).join("|").toUpperCase();',
'  if(/MEANREV|REVERT|CONTRA|FADE/.test(f))return "MEAN_REVERSION";',
'  if(/BREADTH|RELATIVE|BTCALIGN|HYBRID|L2/.test(f))return "RELATIVE";',
'  if(/TREND|MOM|MOMENTUM|FAST/.test(f))return "TREND";',
'  return "GENERIC";',
'}',
'function sideTrendMatch(T,side){return side==="LONG"?T?.trend==="BULLISH":side==="SHORT"?T?.trend==="BEARISH":false;}',
'function adaptiveLocationPolicy(intel,M15,loc,side,context={}){',
'  const mode=profileMode(intel);if(loc?.valid)return {pass:true,mode:"STRUCTURAL_LOCATION",soft:false,level:loc.level};',
'  if(!M15?.ready||!Number.isFinite(M15.atr14)||M15.atr14<=0)return {pass:false,mode,soft:false};',
'  const nearEma=Number.isFinite(M15.ema20)&&Math.abs(M15.close-M15.ema20)<=M15.atr14*.80;',
'  const continuation=side==="LONG"?(M15.bullishBreak||M15.bullishReclaim||sideTrendMatch(M15,side)):(M15.bearishBreak||M15.bearishReclaim||sideTrendMatch(M15,side));',
'  if(mode==="MEAN_REVERSION")return {pass:false,mode,soft:false};',
'  if(mode==="TREND"&&intel.methodFit>=55&&nearEma&&continuation)return {pass:true,mode:"TREND_CONTINUATION_ZONE",soft:true,level:M15.ema20};',
'  if(mode==="RELATIVE"&&intel.methodFit>=52&&Number(context.score||0)>=7&&nearEma&&continuation)return {pass:true,mode:"RELATIVE_CONTINUATION_ZONE",soft:true,level:M15.ema20};',
'  if(mode==="GENERIC"&&intel.methodFit>=68&&nearEma&&(M15.bullishBreak||M15.bearishBreak||M15.bullishReclaim||M15.bearishReclaim))return {pass:true,mode:"QUALITY_CONTINUATION_ZONE",soft:true,level:M15.ema20};',
'  return {pass:false,mode,soft:false,level:Number.isFinite(M15.ema20)?M15.ema20:null};',
'}',
'function adaptiveTriggerPolicy(intel,M5,trig,side,context={}){',
'  const pending=!trig?.valid&&trig?.mss===true&&trig?.displacement===true&&!trig?.retest&&Number.isFinite(trig?.level);',
'  if(trig?.valid)return {pass:true,pending:false,mode:"MSS_DISPLACEMENT_RETEST",level:trig.level};',
'  if(pending)return {pass:true,pending:true,mode:"MSS_DISPLACEMENT_LIMIT",level:trig.level};',
'  const mode=profileMode(intel),r=Number(M5?.rsi14??50),trend=sideTrendMatch(M5,side);',
'  const impulse=side==="LONG"?trend&&r>=51&&r<=76&&M5.close>=M5.ema20:trend&&r<=49&&r>=24&&M5.close<=M5.ema20;',
'  const structuralImpulse=side==="LONG"?(M5.bullishBreak||M5.bullishReclaim):(M5.bearishBreak||M5.bearishReclaim);',
'  if(mode==="MEAN_REVERSION")return {pass:false,pending:false,mode};',
'  if(mode==="TREND"&&intel.methodFit>=60&&impulse&&(structuralImpulse||Math.abs(r-50)>=5))return {pass:true,pending:false,mode:"M5_MOMENTUM_CONTINUATION",level:M5.close,soft:true};',
'  if(mode==="RELATIVE"&&intel.methodFit>=58&&Number(context.score||0)>=7&&impulse&&structuralImpulse)return {pass:true,pending:false,mode:"M5_RELATIVE_BREAK",level:M5.close,soft:true};',
'  if(mode==="GENERIC"&&intel.methodFit>=70&&impulse&&structuralImpulse)return {pass:true,pending:false,mode:"M5_QUALITY_BREAK",level:M5.close,soft:true};',
'  return {pass:false,pending:false,mode,level:trig?.level??null};',
'}',
'function indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior){',
'  if(!M5?.ready||!M15?.ready)return null;let e=Number(locPolicy?.level);if(!Number.isFinite(e))e=Number(M15.ema20);',
'  if(!Number.isFinite(e)||!Number.isFinite(M15.atr14)||Math.abs(e-M15.close)>M15.atr14*1.35)return null;',
'  const p=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!p||p.invalid)return null;',
'  return {entry:p.entry,sl:p.sl,tp1:p.tp1,tp2:p.tp2,targetRR:p.targetRR,tp1RR:p.tp1RR,tp2RR:p.tp2RR,roomR:p.roomR,mode:"INDICATIVE_LIMIT",targetSource:p.targetSource,indicative:true};',
'}',
''
].join('\n');
mustReplace(scoreAnchor,scoreAnchor+adaptiveFns,'adaptive policy insertion');

const deepBlock=[
'async function deepAnalyze(symbol,env,candles=null,reference=null,source=null,context={}){',
'  const s=norm(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};const prior=v73Prior(s,type);',
'  try{if(!candles){if(type==="crypto"){const b=await cryptoDeepBundle(s);candles=b.candles;reference=b.quote;source=b.source;}else candles=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env).then(m=>m.get(s)||[])));}}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"ANALYSIS_DATA_UNAVAILABLE",error:e?.message||String(e)};}',
'  const [m5c,m15c]=candles||[],[M5,M15,H1,H4,D1]=(candles||[]).map(tf);if(!M5||[M5,M15,H1,H4,D1].some(x=>!x?.ready))return watch(s,type,"NEUTRAL","TIMEFRAME_DATA_REQUIRED",{source,score:5,canonical:{v73Prior:prior}});',
'  const intel=methodAssessment(s,type,{M5,M15,H1,H4,D1},context),votes=directionalVotes(D1,H4,H1),side=intel.side,htf=side!=="NEUTRAL"&&((side==="LONG"&&votes.bull>=2)||(side==="SHORT"&&votes.bear>=2));',
'  const base={source,method:intel,context,canonical:{v73Prior:prior},score:setupScore({methodFit:intel.methodFit,htf,htfVotes:Math.max(votes.bull,votes.bear),contextScore:context.score??5})};',
'  if(side==="NEUTRAL"||!htf)return watch(s,type,side,"HTF_METHOD_ALIGNMENT_REQUIRED",base);',
'  const loc=m15Location(m15c,M15,side),locPolicy=adaptiveLocationPolicy(intel,M15,loc,side,context);base.score=setupScore({methodFit:intel.methodFit,htf:true,location:locPolicy.pass,contextScore:context.score??5});',
'  if(!locPolicy.pass){const planned=indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior);return watch(s,type,side,"M15_LOCATION_REQUIRED",{...base,planned,entryPolicy:{profile:profileMode(intel),location:locPolicy},canonical:{...base.canonical,m15Location:loc}});}',
'  const trig=m5Trigger(m5c,M5,side),trigPolicy=adaptiveTriggerPolicy(intel,M5,trig,side,context),pendingRetest=!!trigPolicy.pending;base.score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:trigPolicy.pass&&!pendingRetest,pending:pendingRetest,contextScore:context.score??5});',
'  if(!trigPolicy.pass){const planned=indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior);return watch(s,type,side,"M5_MSS_DISPLACEMENT_RETEST_REQUIRED",{...base,planned,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig}});}',
'  const previewEntry=pendingRetest?Number(trigPolicy.level):M5.close,preview=buildTradePlan(side,previewEntry,M5,M15,H1,H4,D1,pendingRetest,prior);if(!preview)return watch(s,type,side,"STRUCTURAL_SL_REQUIRED",base);if(preview.invalid)return watch(s,type,side,preview.invalid,{...base,roomR:preview.roomR});',
'  const planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,tp1RR:preview.tp1RR,tp2RR:preview.tp2RR,roomR:preview.roomR,mode:preview.mode,targetSource:preview.targetSource,entryStyle:trigPolicy.mode,adaptive:!!(locPolicy.soft||trigPolicy.soft)};',
'  let score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:!pendingRetest,pending:pendingRetest,plan:true,contextScore:context.score??5});',
'  const news=await getNewsClearance(s,env);if(!news)return watch(s,type,side,"NEWS_CONTEXT_REQUIRED",{...base,score,setupReady:true,planned,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:false}}});',
'  score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:!pendingRetest,pending:pendingRetest,plan:true,contextScore:context.score??5,news:true});',
'  if(type!=="crypto")return watch(s,type,side,"EXECUTION_QUOTE_REQUIRED",{...base,score,setupReady:true,planned,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},source:"Twelve Data analysis",canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:true}}});',
'  try{if(!reference)reference=await cryptoExecutionQuote(s);}catch(e){return watch(s,type,side,"FINAL_QUOTE_REQUIRED",{...base,score,setupReady:true,planned,error:e?.message||String(e)});}if(!reference.fresh)return watch(s,type,side,"FINAL_QUOTE_STALE",{...base,score,setupReady:true,planned,quote:reference});if(!reference.executionVerified)return watch(s,type,side,"EXECUTION_QUOTE_REQUIRED",{...base,score,setupReady:true,planned,quote:reference});',
'  const entry=pendingRetest?Number(trigPolicy.level):reference.price,plan=buildTradePlan(side,entry,M5,M15,H1,H4,D1,pendingRetest,prior);if(!plan||plan.invalid)return watch(s,type,side,plan?.invalid||"STRUCTURAL_SL_REQUIRED",{...base,score,setupReady:true,planned,quote:reference});',
'  const spread=reference.ask-reference.bid,costR=spread/plan.risk;if(!Number.isFinite(costR)||costR>CONFIG.maxExecutionCostR)return watch(s,type,side,"EXECUTION_COST_TOO_HIGH",{...base,score,setupReady:true,planned,costR,quote:reference});',
'  score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:true,plan:true,contextScore:context.score??5,news:true,execution:true});',
'  return {ok:true,status:plan.mode,action:plan.mode,symbol:s,market:type,side,score,method:intel,context,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},entry:plan.entry,currentPrice:reference.price,sl:plan.sl,tp1:plan.tp1,tp2:plan.tp2,targetRR:plan.targetRR,tp1RR:plan.tp1RR,tp2RR:plan.tp2RR,roomR:plan.roomR,risk:{riskUsd:CONFIG.defaultRiskUsd,distance:plan.risk,quantity:CONFIG.defaultRiskUsd/plan.risk},quote:reference,source:source||reference.source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true},execution:{verified:true,spread,costR}},engine:CONFIG.version};',
'}',
''
].join('\n');
replaceRange('async function deepAnalyze(','async function quotePool(',deepBlock,'adaptive deepAnalyze');

const oldBroadStart='async function cryptoBroadMap(symbols,env){';
const oldBroadEnd='function changeFromCandles(';
const broadBlock=[
'async function cryptoBroadMap(symbols,env){',
'  let map=await cryptoBulk().catch(()=>new Map());',
'  const cached=await loadCryptoBroadCache(env);for(const [k,q] of cached)if(!map.has(k))map.set(k,q);',
'  // Broad discovery must not exhaust canonical deep venues. Exact probing is emergency-only.',
'  if(map.size<20){',
'    for(const fn of [bybitQuote,okxQuote,binanceQuote]){const missing=symbols.filter(x=>!map.has(x)).slice(0,18);if(!missing.length)break;const exact=await quotePool(missing,fn,2);for(const [k,v] of exact)map.set(k,v);await new Promise(r=>setTimeout(r,220));}',
'  }',
'  for(const [k,q] of map)if(!q.broadCachedAt)map.set(k,{...q,broadCachedAt:Date.now()});',
'  memory.cryptoBulk=map;memory.cryptoBulkAt=Date.now();await saveCryptoBroadCache(env,map);return map;',
'}',
''
].join('\n');
replaceRange(oldBroadStart,oldBroadEnd,broadBlock,'broad/deep separation');

const runBlock=[
'async function runGroup(group,env){',
'  if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group};',
'  const started=Date.now();',
'  try{',
'    const budget=await ensureTdBudget(group,env);',
'    if(!budget.ok){const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;}',
'    const broad=await broadScan(group,env),analyses=[];let deepAttempted=0,skippedUnavailable=[];',
'    if(group==="crypto"){',
'      const shortlist=broad.rows.slice(0,CONFIG.deepShortlist),valid=[];',
'      for(const c of shortlist){',
'        if(Date.now()-started>CONFIG.scanDeadlineMs-2500)break;deepAttempted++;let b;',
'        try{b=await cryptoDeepBundle(c.symbol);}catch(e){skippedUnavailable.push({symbol:c.symbol,reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)});await new Promise(r=>setTimeout(r,CONFIG.cryptoDeepCooldownMs));continue;}',
'        const dc=await cryptoDerivativesContext(c.symbol),a=await deepAnalyze(c.symbol,env,b.candles,b.quote,b.source,{...(c.context||{}),...dc});valid.push(a);',
'        await new Promise(r=>setTimeout(r,CONFIG.cryptoDeepCooldownMs));if(valid.length>=CONFIG.cryptoDeepTarget)break;',
'      }',
'      valid.sort((a,b)=>(Number(b.score)||0)-(Number(a.score)||0));analyses.push(...valid.slice(0,CONFIG.maxCandidates));',
'    }else{',
'      const candidates=broad.rows.slice(0,CONFIG.maxCandidates);let prepared=new Map();try{prepared=await prepareNonCryptoDeep(candidates.map(c=>c.symbol),broad.h1Map,env);}catch{}',
'      for(const c of candidates){if(Date.now()-started>CONFIG.scanDeadlineMs)break;deepAttempted++;const pc=prepared.get(c.symbol);if(!pc)analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"ANALYSIS_DATA_UNAVAILABLE"});else analyses.push(await deepAnalyze(c.symbol,env,pc,null,"Twelve Data",c.context||{}));}',
'    }',
'    const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);',
'    const out={ok:true,version:CONFIG.version,group,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:CONFIG.maxCandidates,deepOk:analyses.filter(a=>a.ok!==false).length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,deepAttempted,skippedUnavailable,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};',
'    await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;',
'  }finally{await releaseLock(env);}',
'}',
''
].join('\n');
replaceRange('async function runGroup(','async function telegram(',runBlock,'resilient candidate router');

// Add direct per-symbol analysis endpoint so every supported symbol can be evaluated on demand.
const symbolFn=[
'async function runSymbol(symbol,env){',
'  const s=norm(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};',
'  if(type==="crypto"){let b;try{b=await cryptoDeepBundle(s);}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)};}let context={score:5};try{const btc= s==="BTCUSDT"?b.quote:await cryptoExecutionQuote("BTCUSDT");const rel=(b.quote.percentChange??0)-(btc.percentChange??0);context={relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel)),...(await cryptoDerivativesContext(s))};}catch{}return deepAnalyze(s,env,b.candles,b.quote,b.source,context);}',
'  const maps=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize)));const candles=maps.map(m=>m.get(s)||[]);return deepAnalyze(s,env,candles,null,"Twelve Data",{score:5});',
'}',
''
].join('\n');
mustReplace('async function telegram(env,method,payload){',symbolFn+'async function telegram(env,method,payload){','runSymbol insertion');

mustReplace('      if(p==="/run-now"){const g=u.searchParams.get("group");return json(await runGroup(g,env));}','      if(p==="/run-now"){const g=u.searchParams.get("group");return json(await runGroup(g,env));}\n      if(p==="/analyze"){const symbol=u.searchParams.get("symbol");return json(await runSymbol(symbol,env));}','analyze endpoint');
mustReplace('endpoints:["/status","/hub","/run-now?group=forex|crypto|metal","/telegram/setup-webhook","/telegram/webhook-info","/telegram/menu","/books"]','endpoints:["/status","/hub","/run-now?group=forex|crypto|metal","/analyze?symbol=BTCUSDT","/telegram/setup-webhook","/telegram/webhook-info","/telegram/menu","/books"]','endpoint listing');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.10.0 adaptive entry freedom + resilient candidate routing');
