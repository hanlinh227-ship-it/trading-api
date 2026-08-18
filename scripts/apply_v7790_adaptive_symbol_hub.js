const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');

function replaceRange(start,end,repl,label){
  const a=s.indexOf(start); if(a<0) throw new Error('Missing start '+label+': '+start);
  const b=s.indexOf(end,a+start.length); if(b<0) throw new Error('Missing end '+label+': '+end);
  s=s.slice(0,a)+repl+s.slice(b);
}
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

s=s.replaceAll('V77.8.0','V77.9.0').replaceAll('V77.8.1','V77.9.0');
s=s.replaceAll('Trading V77.8.0 Unified Canonical Hub','Trading V77.9.0 Adaptive Symbol Intelligence Hub');
s=s.replaceAll('Trading V77.8.1 Unified Canonical Hub','Trading V77.9.0 Adaptive Symbol Intelligence Hub');

const priorBlock=`function v73Entry(symbol,type){
  let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=norm(symbol).replace(/USDT$/,"");if(!key)return null;
  return V73_CONFIG?.[type]?.symbols?.[key]||null;
}
function v73Prior(symbol,type){
  const e=v73Entry(symbol,type);let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=norm(symbol).replace(/USDT$/,"");
  if(!key)return {applicable:false,available:false};if(!e)return {applicable:true,available:false,key};
  const m=e.method||{},st=m.style||{},actions=Array.isArray(m.actions)?m.actions:[];
  const families=[...new Set([st.family,m.profile,...actions.map(a=>a.family)].filter(Boolean))];
  return {applicable:true,available:true,key,source:e.source,timeframe:e.timeframe,status:m.status,family:st.family||m.profile||(m.router?"ROUTER":null),families,profile:m.profile||null,entryMode:st.entryMode||(m.router?"ROUTER":null),rr:st.rr??null,signalHourUTC:st.signalHourUTC??m.decisionHourUTC??null,riskATR:st.riskATR??null,newsProfile:e.newsProfile||null,classification:V73_CONFIG.classification};
}
function directionalVotes(D1,H4,H1){
  const arr=[D1,H4,H1],bull=arr.filter(x=>x.trend==="BULLISH").length,bear=arr.filter(x=>x.trend==="BEARISH").length;
  return {bull,bear,side:bull>=2?"LONG":bear>=2?"SHORT":"NEUTRAL"};
}
function sessionFit(prior){
  if(!Number.isFinite(Number(prior?.signalHourUTC)))return 0.6;
  const h=new Date().getUTCHours(),d=Math.min((h-prior.signalHourUTC+24)%24,(prior.signalHourUTC-h+24)%24);
  return Math.max(0.15,1-d/12);
}
function methodAssessment(symbol,type,T,context={}){
  const {M5,M15,H1,H4,D1}=T,prior=v73Prior(symbol,type),votes=directionalVotes(D1,H4,H1),fam=(prior.families||[]).join('|').toUpperCase();
  let side=votes.side,fit=50,why=[];
  const longMom=(H1.rsi14??50)>=52&&H1.close>(H1.ema20??H1.close),shortMom=(H1.rsi14??50)<=48&&H1.close<(H1.ema20??H1.close);
  if(/TREND|MOM|MOMENTUM|FAST/.test(fam)){
    fit=35+15*Math.max(votes.bull,votes.bear)/3+10*(side==="LONG"?longMom:side==="SHORT"?shortMom:false);
    why.push('trend/momentum profile');
  }else if(/CONTRA|FADE|SLOW|SESSION/.test(fam)){
    const ext=Math.abs((H1.rsi14??50)-50)/50;fit=40+20*Math.min(1,ext)+10*sessionFit(prior);why.push('fade/session profile');
  }else if(/BREADTH|RELATIVE|HYBRID|L2/.test(fam)){
    fit=45+15*Math.min(1,Math.abs(Number(context.relativeStrength??context.strengthDiff??0))/2);why.push('relative/breadth profile');
  }else{fit=45+15*Math.max(votes.bull,votes.bear)/3;why.push('generic frozen profile');}
  if(side==="NEUTRAL"&&H4.trend===H1.trend&&H1.trend!=="NEUTRAL")side=H1.trend==="BULLISH"?"LONG":"SHORT";
  if(type==="forex"&&Number.isFinite(context.strengthDiff)){
    const ctxSide=context.strengthDiff>0?"LONG":context.strengthDiff<0?"SHORT":"NEUTRAL";
    if(ctxSide===side)fit+=12;else if(ctxSide!=="NEUTRAL"&&side!=="NEUTRAL")fit-=10;
    why.push('currency-strength context');
  }
  if(type==="crypto"&&Number.isFinite(context.relativeStrength)){
    if((side==="LONG"&&context.relativeStrength>0)||(side==="SHORT"&&context.relativeStrength<0))fit+=10;else if(side!=="NEUTRAL")fit-=5;
    if(Number.isFinite(context.fundingRate)&&Math.abs(context.fundingRate)>0.0015)fit-=6;
    why.push('BTC-relative + derivatives context');
  }
  if(type==="metal"&&Number.isFinite(context.relativeStrength)){
    if((side==="LONG"&&context.relativeStrength>0)||(side==="SHORT"&&context.relativeStrength<0))fit+=8;
    why.push('relative-metal context');
  }
  fit=Math.max(0,Math.min(100,Math.round(fit)));
  return {side,methodFit:fit,profile:prior.profile||prior.family||"GENERIC",families:prior.families||[],sessionFit:Math.round(sessionFit(prior)*100),why,drivers:prior.newsProfile?.profileDrivers||prior.newsProfile?.symbolSpecific||[]};
}
function setupScore(parts={}){
  let x=0;x+=Math.min(25,(parts.methodFit||0)*0.25);x+=parts.htf?20:Math.min(12,(parts.htfVotes||0)*4);x+=parts.location?15:0;x+=parts.trigger?15:parts.pending?8:0;x+=parts.plan?10:0;x+=Math.min(10,Math.max(0,parts.contextScore??5));x+=parts.news?3:0;x+=parts.execution?2:0;return Math.max(0,Math.min(100,Math.round(x)));
}
`;
replaceRange('function v73Prior(', 'function watch(', priorBlock+'function watch(', 'v73 intelligence');

const planBlock=`function structuralCandidates(side,M5,M15,H1,H4,D1){
  const lowSide=side==="LONG",raw=lowSide?[M5.liquidityLow20,M15.liquidityLow20,H1.liquidityLow20,H4.liquidityLow20,D1.liquidityLow20]:[M5.liquidityHigh20,M15.liquidityHigh20,H1.liquidityHigh20,H4.liquidityHigh20,D1.liquidityHigh20];
  return raw.filter(Number.isFinite);
}
function targetCandidates(side,entry,M15,H1,H4,D1){
  const raw=side==="LONG"?[M15.liquidityHigh20,H1.liquidityHigh20,H4.liquidityHigh20,D1.liquidityHigh20]:[M15.liquidityLow20,H1.liquidityLow20,H4.liquidityLow20,D1.liquidityLow20];
  return [...new Set(raw.filter(Number.isFinite).filter(v=>side==="LONG"?v>entry:v<entry))].sort((a,b)=>Math.abs(a-entry)-Math.abs(b-entry));
}
function buildTradePlan(side,entry,M5,M15,H1,H4,D1,pendingRetest,prior={}){
  const atrFloor=Math.max(M5.atr14*.55,(Number(prior.riskATR)||0.55)*M5.atr14*.7),structures=structuralCandidates(side,M5,M15,H1,H4,D1);
  let anchor=null;if(structures.length)anchor=side==="LONG"?Math.max(...structures.filter(v=>v<entry)):Math.min(...structures.filter(v=>v>entry));
  if(!Number.isFinite(anchor))anchor=side==="LONG"?entry-atrFloor:entry+atrFloor;
  const buffer=M5.atr14*.12,sl=side==="LONG"?Math.min(anchor-buffer,entry-atrFloor):Math.max(anchor+buffer,entry+atrFloor),risk=Math.abs(entry-sl);
  if(!Number.isFinite(risk)||risk<=0)return null;
  const targets=targetCandidates(side,entry,M15,H1,H4,D1),valid=targets.map(v=>({price:v,rr:Math.abs(v-entry)/risk})).filter(x=>x.rr>=0.85&&x.rr<=5);
  if(!valid.length)return {invalid:"CLEAN_TARGET_REQUIRED",risk,roomR:0};
  const tp1=valid[0],tp2=valid.find(x=>x.rr>=Math.max(1.5,tp1.rr+.35))||valid.at(-1),best=tp2||tp1;
  return {entry,sl,risk,roomR:best.rr,targetRR:Number(best.rr.toFixed(2)),tp1:tp1.price,tp1RR:Number(tp1.rr.toFixed(2)),tp2:best.price,tp2RR:Number(best.rr.toFixed(2)),mode:pendingRetest?"LIMIT":"MARKET",targetSource:"STRUCTURE_LIQUIDITY"};
}
`;
replaceRange('function buildTradePlan(', 'async function deepAnalyze(', planBlock+'async function deepAnalyze(', 'dynamic plan');

const deepBlock=`async function deepAnalyze(symbol,env,candles=null,reference=null,source=null,context={}){
  const s=norm(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};
  const prior=v73Prior(s,type);
  try{if(!candles){if(type==="crypto"){const b=await cryptoDeepBundle(s);candles=b.candles;reference=b.quote;source=b.source;}else candles=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env).then(m=>m.get(s)||[])));}}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"ANALYSIS_DATA_UNAVAILABLE",error:e?.message||String(e)};}
  const [m5c,m15c,h1c,h4c,d1c]=candles||[],[M5,M15,H1,H4,D1]=(candles||[]).map(tf);
  if(!M5||[M5,M15,H1,H4,D1].some(x=>!x?.ready))return watch(s,type,"NEUTRAL","TIMEFRAME_DATA_REQUIRED",{source,score:5,canonical:{v73Prior:prior}});
  const intel=methodAssessment(s,type,{M5,M15,H1,H4,D1},context),votes=directionalVotes(D1,H4,H1),side=intel.side,htf=side!=="NEUTRAL"&&((side==="LONG"&&votes.bull>=2)||(side==="SHORT"&&votes.bear>=2));
  const base={source,method:intel,context,canonical:{v73Prior:prior},score:setupScore({methodFit:intel.methodFit,htf,htfVotes:Math.max(votes.bull,votes.bear),contextScore:context.score??5})};
  if(side==="NEUTRAL"||!htf)return watch(s,type,side,"HTF_METHOD_ALIGNMENT_REQUIRED",base);
  const loc=m15Location(m15c,M15,side);base.score=setupScore({methodFit:intel.methodFit,htf:true,location:loc.valid,contextScore:context.score??5});if(!loc.valid)return watch(s,type,side,"M15_LOCATION_REQUIRED",{...base,canonical:{...base.canonical,m15Location:loc}});
  const trig=m5Trigger(m5c,M5,side),pendingRetest=!trig.valid&&trig.mss===true&&trig.displacement===true&&!trig.retest&&Number.isFinite(trig.level);base.score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:trig.valid,pending:pendingRetest,contextScore:context.score??5});
  if(!trig.valid&&!pendingRetest)return watch(s,type,side,"M5_MSS_DISPLACEMENT_RETEST_REQUIRED",{...base,canonical:{...base.canonical,m15Location:loc,m5Trigger:trig}});
  const previewEntry=pendingRetest?Number(trig.level):M5.close,preview=buildTradePlan(side,previewEntry,M5,M15,H1,H4,D1,pendingRetest,prior);
  if(!preview)return watch(s,type,side,"STRUCTURAL_SL_REQUIRED",base);if(preview.invalid)return watch(s,type,side,preview.invalid,{...base,roomR:preview.roomR});
  const planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,tp1RR:preview.tp1RR,tp2RR:preview.tp2RR,roomR:preview.roomR,mode:preview.mode,targetSource:preview.targetSource};
  let score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:trig.valid,pending:pendingRetest,plan:true,contextScore:context.score??5});
  const news=await getNewsClearance(s,env);if(!news)return watch(s,type,side,"NEWS_CONTEXT_REQUIRED",{...base,score,setupReady:true,planned,canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:false}}});
  score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:trig.valid,pending:pendingRetest,plan:true,contextScore:context.score??5,news:true});
  if(type!=="crypto")return watch(s,type,side,"EXECUTION_QUOTE_REQUIRED",{...base,score,setupReady:true,planned,source:"Twelve Data analysis",canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,news:{cleared:true}}});
  try{if(!reference)reference=await cryptoExecutionQuote(s);}catch(e){return watch(s,type,side,"FINAL_QUOTE_REQUIRED",{...base,score,setupReady:true,planned,error:e?.message||String(e)});}if(!reference.fresh)return watch(s,type,side,"FINAL_QUOTE_STALE",{...base,score,setupReady:true,planned,quote:reference});if(!reference.executionVerified)return watch(s,type,side,"EXECUTION_QUOTE_REQUIRED",{...base,score,setupReady:true,planned,quote:reference});
  const entry=pendingRetest?Number(trig.level):reference.price,plan=buildTradePlan(side,entry,M5,M15,H1,H4,D1,pendingRetest,prior);if(!plan||plan.invalid)return watch(s,type,side,plan?.invalid||"STRUCTURAL_SL_REQUIRED",{...base,score,setupReady:true,planned,quote:reference});
  const spread=reference.ask-reference.bid,costR=spread/plan.risk;if(!Number.isFinite(costR)||costR>CONFIG.maxExecutionCostR)return watch(s,type,side,"EXECUTION_COST_TOO_HIGH",{...base,score,setupReady:true,planned,costR,quote:reference});
  score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:true,plan:true,contextScore:context.score??5,news:true,execution:true});
  return {ok:true,status:plan.mode,action:plan.mode,symbol:s,market:type,side,score,method:intel,context,entry:plan.entry,currentPrice:reference.price,sl:plan.sl,tp1:plan.tp1,tp2:plan.tp2,targetRR:plan.targetRR,tp1RR:plan.tp1RR,tp2RR:plan.tp2RR,roomR:plan.roomR,risk:{riskUsd:CONFIG.defaultRiskUsd,distance:plan.risk,quantity:CONFIG.defaultRiskUsd/plan.risk},quote:reference,source:source||reference.source,canonical:{v73Prior:prior,m15Location:loc,m5Trigger:trig,news:{cleared:true},execution:{verified:true,spread,costR}},engine:CONFIG.version};
}
`;
replaceRange('async function deepAnalyze(', 'function broadRank(', deepBlock+'function broadRank(', 'adaptive deepAnalyze');

const contextHelpers=`function changeFromCandles(c){if(!Array.isArray(c)||c.length<2)return 0;const a=c.at(-2)?.close,b=c.at(-1)?.close;return a?((b-a)/a)*100:0;}
function forexStrengthMap(h1Map){const sum={},cnt={};for(const [sym,c] of h1Map.entries()){if(!Array.isArray(c)||c.length<2)continue;const ch=changeFromCandles(c),base=sym.slice(0,3),quote=sym.slice(3);sum[base]=(sum[base]||0)+ch;cnt[base]=(cnt[base]||0)+1;sum[quote]=(sum[quote]||0)-ch;cnt[quote]=(cnt[quote]||0)+1;}const out={};for(const k of Object.keys(sum))out[k]=sum[k]/Math.max(1,cnt[k]);return out;}
async function cryptoDerivativesContext(symbol){
  try{const p=await bybit("/v5/market/tickers",{category:"linear",symbol:norm(symbol)}),r=p?.result?.list?.[0];if(!r||norm(r.symbol)!==norm(symbol))return {};return {fundingRate:num(r.fundingRate),openInterest:num(r.openInterest),turnover24h:num(r.turnover24h)};}catch{return {};}
}
`;
replaceRange('function broadRank(', 'async function broadScan(', contextHelpers+'function broadRank(q){if(!q?.price)return 0;let x=0;if(q.open)x+=Math.abs((q.price-q.open)/q.open)*100;if(Number.isFinite(q.percentChange))x+=Math.abs(q.percentChange);return x;}\nasync function broadScan(', 'context helpers');

const broadBlock=`async function broadScan(group,env){
  const symbols=GROUPS[group],rows=[],errors=[];
  if(group==="crypto"){
    const bulk=await cryptoBulk().catch(()=>new Map()),btc=bulk.get("BTCUSDT")?.percentChange??0;
    for(const sym of symbols){const q=bulk.get(sym);if(q?.price){const rel=(q.percentChange??0)-btc;rows.push({symbol:sym,quote:q,strength:broadRank(q),context:{relativeStrength:rel,benchmark:"BTC",score:Math.min(10,5+Math.abs(rel))}});}else errors.push({symbol:sym,reason:"EXACT_SPOT_UNAVAILABLE"});}
    rows.sort((a,b)=>b.strength-a.strength);return {requested:symbols.length,rows,errors,h1Map:null};
  }
  let h1Map=new Map();try{h1Map=await tdBatchCandles(symbols,"1h",env,60);}catch(e){return {requested:symbols.length,rows,errors:symbols.map(symbol=>({symbol,reason:"H1_BATCH_UNAVAILABLE",error:e?.message||String(e)})),h1Map};}
  const fx=group==="forex"?forexStrengthMap(h1Map):{};
  let metalMoves={};if(group==="metal")for(const sym of symbols)metalMoves[sym]=changeFromCandles(h1Map.get(sym)||[]);
  for(const sym of symbols){const T=tf(h1Map.get(sym)||[]);if(!T.ready){errors.push({symbol:sym,reason:"H1_UNAVAILABLE"});continue;}let context={score:5};if(group==="forex"){const base=sym.slice(0,3),quote=sym.slice(3),d=(fx[base]||0)-(fx[quote]||0);context={baseStrength:fx[base]||0,quoteStrength:fx[quote]||0,strengthDiff:d,score:Math.min(10,5+Math.abs(d)*4)};}else{const other=sym==="XAUUSD"?"XAGUSD":"XAUUSD",rel=(metalMoves[sym]||0)-(metalMoves[other]||0);context={relativeStrength:rel,benchmark:other,score:Math.min(10,5+Math.abs(rel)*3)};}rows.push({symbol:sym,quote:{source:"Twelve Data H1",price:T.close,fresh:true},strength:Math.abs((T.close-(T.ema20??T.close))/(T.atr14||1)),context});}
  rows.sort((a,b)=>b.strength-a.strength);return {requested:symbols.length,rows,errors,h1Map};
}
`;
replaceRange('async function broadScan(', 'async function prepareNonCryptoDeep(', broadBlock+'async function prepareNonCryptoDeep(', 'adaptive broadScan');

// Pass candidate-specific context and crypto derivatives context into deep analysis.
s=s.replace('else analyses.push(await deepAnalyze(c.symbol,env,b.candles,b.quote,b.source));','else{const dc=await cryptoDerivativesContext(c.symbol);analyses.push(await deepAnalyze(c.symbol,env,b.candles,b.quote,b.source,{...(c.context||{}),...dc}));}');
s=s.replace('else analyses.push(await deepAnalyze(c.symbol,env,pc,null,"Twelve Data"));','else analyses.push(await deepAnalyze(c.symbol,env,pc,null,"Twelve Data",c.context||{}));');

// Harden old books: only crypto may retain executable positions and they must have complete prices.
replaceRange('function normalizeBooks(', 'async function getBooks(', `function validExecutablePosition(p,group){if(group!=="crypto"||!p||typeof p!=="object")return false;if(!CRYPTO.includes(norm(p.symbol))||!["LONG","SHORT"].includes(p.side))return false;return [p.entry,p.sl,p.tp].every(v=>Number.isFinite(Number(v))&&Number(v)>0);}\nfunction normalizeBooks(v){const b=emptyBooks();if(!v||typeof v!=="object")return b;for(const g of Object.keys(GROUPS)){const src=v?.[g]||{};if(g==="crypto"){b[g].marketActive=Array.isArray(src.marketActive)?src.marketActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxMarketActive):[];b[g].limitActive=Array.isArray(src.limitActive)?src.limitActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxLimitActive):[];b[g].limitPending=Array.isArray(src.limitPending)?src.limitPending.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxPendingLimit):[];}b[g].watch=Array.isArray(src.watch)?src.watch.filter(w=>GROUPS[g].includes(norm(w.symbol))).slice(0,CONFIG.maxWatch):[];}b.updatedAt=v.updatedAt||Date.now();return b;}\nasync function getBooks(`, 'book cleanup');

const uiBlock=`function fmtPx(v){const n=Number(v);if(!Number.isFinite(n))return "—";if(Math.abs(n)>=1000)return n.toFixed(2);if(Math.abs(n)>=10)return n.toFixed(4);if(Math.abs(n)>=1)return n.toFixed(5);return n.toPrecision(6);}
function reasonText(r){return ({HTF_METHOD_ALIGNMENT_REQUIRED:"Chờ phương pháp riêng + HTF đồng thuận",HTF_ALIGNMENT_REQUIRED:"Chờ D1/H4/H1 đồng thuận",M15_LOCATION_REQUIRED:"Chờ giá vào vùng M15 đẹp",M5_MSS_DISPLACEMENT_RETEST_REQUIRED:"Chờ trigger M5",STRUCTURAL_SL_REQUIRED:"Chưa có SL cấu trúc",CLEAN_TARGET_REQUIRED:"Chưa có mục tiêu thanh khoản đủ tốt",NEWS_CONTEXT_REQUIRED:"Chờ tin/context",EXECUTION_QUOTE_REQUIRED:"Chờ bid/ask thực",FINAL_QUOTE_REQUIRED:"Chờ giá execution",FINAL_QUOTE_STALE:"Giá execution cũ",EXECUTION_COST_TOO_HIGH:"Spread/chi phí cao",TIMEFRAME_DATA_REQUIRED:"Thiếu timeframe",ANALYSIS_DATA_UNAVAILABLE:"Thiếu dữ liệu"})[r]||"Chờ thêm xác nhận";}
function stageText(a){if(a.status==="MARKET")return "🟢 MARKET";if(a.status==="LIMIT")return "🟡 LIMIT";if(a.reason==="NEWS_CONTEXT_REQUIRED")return "🟠 ARMED";if(a.reason==="EXECUTION_QUOTE_REQUIRED"||a.reason==="FINAL_QUOTE_REQUIRED")return "🔵 READY";if(a.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")return "🟣 SETUP";return "⚪ WATCH";}
function posLine(p){return `${p.symbol} ${sideText(p.side)} • E ${fmtPx(p.entry)} • SL ${fmtPx(p.sl)} • TP ${fmtPx(p.tp)}`;}
function watchLine(w){let x=`${w.symbol} ${sideText(w.side)} • ${reasonText(w.reason)}`;if(Number.isFinite(w.score))x+=` • ${w.score}/100`;if(w.planned)x+=`\n   ↳ E~${fmtPx(w.planned.entry)} • SL~${fmtPx(w.planned.sl)} • TP~${fmtPx(w.planned.tp2||w.planned.tp1)} • RR~${Number(w.planned.targetRR||0).toFixed(2)}`;if(w.method?.profile)x+=`\n   ↳ ${w.method.profile}`;return x;}
`;
replaceRange('function fmtPx(', 'function summary(', uiBlock+'function summary(', 'Hub UI');

// Store score/method/context in watch books.
s=s.replace('source:x.source||null,updatedAt:Date.now(),engine:CONFIG.version','source:x.source||null,score:x.score??null,method:x.method||null,context:x.context||null,updatedAt:Date.now(),engine:CONFIG.version');

// Rank Hub by normalized score first, canonical readiness second.
replaceRange('function hubRank(', 'async function runHub(', `function hubRank(a){const base=Number(a.score)||0;if(a.status==="MARKET")return 200+base;if(a.status==="LIMIT")return 190+base;if(a.reason==="EXECUTION_QUOTE_REQUIRED"||a.reason==="FINAL_QUOTE_REQUIRED")return 170+base;if(a.reason==="NEWS_CONTEXT_REQUIRED")return 160+base;if(a.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")return 120+base;if(a.reason==="M15_LOCATION_REQUIRED")return 90+base;return base;}\nasync function runHub(`, 'Hub rank');

replaceRange('function hubSummary(', 'async function sendHub(', `function hubSummary(h){const L=[\`🧭 TRADING HUB ${CONFIG.version}\`,"","🔥 TOP SETUPS"];if(!h.top.length)L.push("Không có setup đạt chuẩn lúc này.");h.top.slice(0,5).forEach((a,i)=>{let line=\`${i+1}. ${a.symbol} ${sideText(a.side)} • ${stageText(a)} • ${Number(a.score)||0}/100\`;if(a.method?.profile||a.method?.families?.length)line+=\`\n   ↳ Method: ${a.method?.profile||a.method?.families?.[0]}\`;if(a.planned)line+=\`\n   ↳ E~${fmtPx(a.planned.entry)} • SL~${fmtPx(a.planned.sl)} • TP~${fmtPx(a.planned.tp2||a.planned.tp1)} • RR~${Number(a.planned.targetRR||0).toFixed(2)}\`;line+=\`\n   ↳ ${a.status==="WATCH"?reasonText(a.reason):"Đủ gate execution"}\`;L.push(line);});L.push("","Điểm Hub = độ hoàn thiện setup, KHÔNG phải xác suất thắng.");for(const g of ["forex","crypto","metal"]){const r=h.runs[g];L.push(\`${groupTitle(g)} • ${r.status==="RATE_BUDGET_WAIT"?"đợi quota":`${r.broadOk}/${r.requested} • deep ${r.deepOk}/${r.deepRequested}`}\`);}return L.join("\\n");}\nasync function sendHub(`, 'Hub summary');

// Keep Telegram messages safely below the API limit.
if(!s.includes('function telegramSafeText('))s=s.replace('async function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}','function telegramSafeText(text){const x=String(text??"");return x.length<=3900?x:x.slice(0,3860)+"\\n… đã rút gọn";}\nasync function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text:telegramSafeText(text),reply_markup,disable_web_page_preview:true});}');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.9.0 Adaptive Symbol Intelligence Hub');