const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function must(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

must('import V73_CONFIG from "../data/nocut_intraday_allpass_v73.json" with { type: "json" };','import V73_CONFIG from "../data/nocut_intraday_allpass_v73.json" with { type: "json" };\nimport SYMBOL_KNOWLEDGE from "../data/symbol_knowledge_registry.json" with { type: "json" };','knowledge import');
s=s.replaceAll('V77.12.0','V77.13.0');
s=s.replaceAll('Trading V77.13.0 Fresh Scan Persistent Order Hub','Trading V77.13.0 Calibrated Adaptive Entry Hub');
must('orderHistory: "v7712:order_history",','orderHistory: "v7712:order_history",\n    shadowSetups: "v7713:shadow_setups",','shadow key');

const oldPlan='const valid=targetCandidates(side,entry,M15,H1,H4,D1).map(v=>({price:v,rr:Math.abs(v-entry)/risk})).filter(x=>x.rr>=.85&&x.rr<=5);if(!valid.length)return {invalid:"CLEAN_TARGET_REQUIRED",risk,roomR:0};\n  const tp1=valid[0],tp2=valid.find(x=>x.rr>=Math.max(1.5,tp1.rr+.35))||valid.at(-1),best=tp2||tp1;return {entry,sl,risk,roomR:best.rr,targetRR:Number(best.rr.toFixed(2)),tp1:tp1.price,tp1RR:Number(tp1.rr.toFixed(2)),tp2:best.price,tp2RR:Number(best.rr.toFixed(2)),mode:pendingRetest?"LIMIT":"MARKET",targetSource:"STRUCTURE_LIQUIDITY"};';
const newPlan='const valid=targetCandidates(side,entry,M15,H1,H4,D1).map(v=>({price:v,rr:Math.abs(v-entry)/risk})).filter(x=>x.rr>=.80&&x.rr<=4);if(!valid.length)return {invalid:"CLEAN_TARGET_REQUIRED",risk,roomR:0};\n  const tp1=valid[0],tp2=valid.find(x=>x.rr>=Math.max(1.4,tp1.rr+.35)&&x.rr<=3.2)||null,best=tp2||tp1;return {entry,sl,risk,roomR:best.rr,targetRR:Number(best.rr.toFixed(2)),tp1:tp1.price,tp1RR:Number(tp1.rr.toFixed(2)),tp2:(tp2||tp1).price,tp2RR:Number((tp2||tp1).rr.toFixed(2)),mode:pendingRetest?"LIMIT":"MARKET",targetSource:"STRUCTURE_LIQUIDITY",targetTier:tp2?"PRIMARY_PLUS_EXTENSION":"PRIMARY_ONLY"};';
must(oldPlan,newPlan,'realistic target selection');

const insertBefore='async function deepAnalyze(symbol,env,candles=null,reference=null,source=null,context={}){';
const helpers=[
'function symbolKnowledge(symbol){const s=canonicalUserSymbol(symbol),k=s.endsWith("USDT")?s.slice(0,-4):s;return SYMBOL_KNOWLEDGE?.symbols?.[s]||SYMBOL_KNOWLEDGE?.symbols?.[k]||null;}',
'function minimumQualityRR(intel){const mode=profileMode(intel);let x=mode==="MEAN_REVERSION"?1.0:mode==="TREND"?1.2:mode==="RELATIVE"?1.15:1.25;if(Number(intel?.methodFit)>=85)x-=.1;return Math.max(1,Number(x.toFixed(2)));}',
'function rrQuality(plan,intel){const min=minimumQualityRR(intel),rr=Number(plan?.targetRR);return {pass:Number.isFinite(rr)&&rr>=min,minRR:min,targetRR:rr};}',
''
].join('\n');
if(!s.includes(insertBefore))throw new Error('Missing deepAnalyze marker');s=s.replace(insertBefore,helpers+insertBefore);

must('const s=canonicalUserSymbol(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};const prior=v73Prior(s,type);','const s=canonicalUserSymbol(symbol),type=marketType(s);if(type==="unknown")return {ok:false,status:"DATA_BLOCK",symbol:s,reason:"UNSUPPORTED_SYMBOL"};const prior=v73Prior(s,type),knowledge=symbolKnowledge(s);','knowledge in deep');
must('const base={source,method:intel,context,canonical:{v73Prior:prior},score:setupScore({methodFit:intel.methodFit,htf,htfVotes:Math.max(votes.bull,votes.bear),contextScore:context.score??5})};','const base={source,method:intel,knowledge:knowledge?{canonicalSymbol:knowledge.canonicalSymbol,allowedModes:knowledge.allowedModes,riskATR:knowledge.riskATR,newsProfile:knowledge.newsProfile,calibration:knowledge.calibration}:null,context,canonical:{v73Prior:prior},score:setupScore({methodFit:intel.methodFit,htf,htfVotes:Math.max(votes.bull,votes.bear),contextScore:context.score??5})};','knowledge base');
must('const planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,tp1RR:preview.tp1RR,tp2RR:preview.tp2RR,roomR:preview.roomR,mode:preview.mode,targetSource:preview.targetSource,entryStyle:trigPolicy.mode,adaptive:!!(locPolicy.soft||trigPolicy.soft)};\n  let score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:!pendingRetest,pending:pendingRetest,plan:true,contextScore:context.score??5});','const quality=rrQuality(preview,intel),planned={entry:preview.entry,sl:preview.sl,tp1:preview.tp1,tp2:preview.tp2,targetRR:preview.targetRR,tp1RR:preview.tp1RR,tp2RR:preview.tp2RR,roomR:preview.roomR,mode:preview.mode,targetSource:preview.targetSource,targetTier:preview.targetTier,entryStyle:trigPolicy.mode,adaptive:!!(locPolicy.soft||trigPolicy.soft),minQualityRR:quality.minRR,rrQualityPass:quality.pass};\n  let score=setupScore({methodFit:intel.methodFit,htf:true,location:true,trigger:!pendingRetest,pending:pendingRetest,plan:true,contextScore:context.score??5});\n  if(!quality.pass)return watch(s,type,side,"RR_QUALITY_REQUIRED",{...base,score,setupReady:true,planned,entryPolicy:{profile:profileMode(intel),location:locPolicy,trigger:trigPolicy},canonical:{...base.canonical,m15Location:loc,m5Trigger:trig,rrQuality:quality}});','rr quality gate');

must('EXECUTION_COST_TOO_HIGH:"Spread/chi phí cao",TIMEFRAME_DATA_REQUIRED','EXECUTION_COST_TOO_HIGH:"Spread/chi phí cao",RR_QUALITY_REQUIRED:"RR cấu trúc chưa đủ tốt",TIMEFRAME_DATA_REQUIRED','reason text');

const shadowFns=[
'async function recordShadowSetup(group,a,scanId,env){',
'  if(!a||a.status!=="WATCH"||!a.planned||!["LONG","SHORT"].includes(a.side))return;',
'  const rr=Number(a.planned.targetRR);if(!Number.isFinite(rr)||rr<1)return;',
'  try{const old=await env.TRADING_STATE.get(CONFIG.keys.shadowSetups,"json"),rows=Array.isArray(old?.rows)?old.rows:[],mode=a.method?.activeMode||a.entryPolicy?.profile||"GENERIC",now=Date.now();',
'    const duplicate=rows.some(x=>x.status==="OPEN"&&x.symbol===a.symbol&&x.mode===mode&&now-Number(x.createdAt)<30*60000);if(duplicate)return;',
'    rows.unshift({id:a.symbol+"-"+now,symbol:a.symbol,group,side:a.side,mode,score:a.score??null,entry:a.planned.entry,sl:a.planned.sl,tp1:a.planned.tp1,tp2:a.planned.tp2,targetRR:a.planned.targetRR,minQualityRR:a.planned.minQualityRR??minimumQualityRR(a.method),reason:a.reason,source:a.source||null,scanId:scanId||null,createdAt:now,expiresAt:now+(group==="forex"?12:8)*3600000,status:"OPEN",calibrationStatus:a.knowledge?.calibration?.status||"UNVERIFIED"});',
'    await env.TRADING_STATE.put(CONFIG.keys.shadowSetups,JSON.stringify({rows:rows.slice(0,500),updatedAt:now}));}catch{}',
'}',
'async function getShadowSetups(env,symbol=null){try{const v=await env.TRADING_STATE.get(CONFIG.keys.shadowSetups,"json");const rows=Array.isArray(v?.rows)?v.rows:[];return symbol?rows.filter(x=>x.symbol===canonicalUserSymbol(symbol)):rows;}catch{return [];}}',
''
].join('\n');
const lockMarker='async function acquireLock(env){';if(!s.includes(lockMarker))throw new Error('Missing lock marker');s=s.replace(lockMarker,shadowFns+lockMarker);

must('const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);','const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);for(const a of analyses)await recordShadowSetup(group,a,scanId,env);','shadow from group scan');

must('if(a.method?.profile)L.push(`Profile: ${a.method.profile}`);if(a.method?.activeMode)L.push(`Active route: ${a.method.activeMode}${a.method.allowedModes?.length>1?" (allowed: "+a.method.allowedModes.join("/")+")":""}`);','if(a.method?.profile)L.push(`Profile: ${a.method.profile}`);if(a.method?.activeMode)L.push(`Active route: ${a.method.activeMode}${a.method.allowedModes?.length>1?" (allowed: "+a.method.allowedModes.join("/")+")":""}`);if(a.knowledge?.calibration?.status)L.push(`Calibration: ${a.knowledge.calibration.status}`);','calibration UI');

must('if(p==="/books"||p==="/orders")return json(await getBooks(env));','if(p==="/books"||p==="/orders")return json(await getBooks(env));\n      if(p==="/knowledge"){const symbol=canonicalUserSymbol(u.searchParams.get("symbol"));return json({ok:true,symbol,knowledge:symbolKnowledge(symbol)});}\n      if(p==="/shadow"){const symbol=u.searchParams.get("symbol");return json({ok:true,rows:await getShadowSetups(env,symbol)});}','knowledge shadow endpoints');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.13.0 calibration and RR quality layer');
