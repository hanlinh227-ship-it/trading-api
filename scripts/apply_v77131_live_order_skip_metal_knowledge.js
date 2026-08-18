const fs=require('fs');
const worker='cloudflare-worker/index.js';
const knowledgePath='data/symbol_knowledge_registry.json';
let s=fs.readFileSync(worker,'utf8');
function must(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

s=s.replaceAll('V77.13.0','V77.13.1');
s=s.replaceAll('Trading V77.13.1 Calibrated Adaptive Entry Hub','Trading V77.13.1 Calibrated Adaptive Entry Hub');

// Do not deep-analyze a symbol that already has a durable active/pending executable order.
must('const broad=await broadScan(group,env),analyses=[];let deepAttempted=0,skippedUnavailable=[];','const broad=await broadScan(group,env),analyses=[];let deepAttempted=0,skippedUnavailable=[];\n    const existingBooks=await getBooks(env),liveSymbols=new Set([...(existingBooks[group]?.marketActive||[]),...(existingBooks[group]?.limitActive||[]),...(existingBooks[group]?.limitPending||[])].map(x=>canonicalUserSymbol(x.symbol)));\n    const entryRows=broad.rows.filter(x=>!liveSymbols.has(canonicalUserSymbol(x.symbol)));','exclude live symbols');
must('const shortlist=broad.rows.slice(0,CONFIG.deepShortlist),valid=[];','const shortlist=entryRows.slice(0,CONFIG.deepShortlist),valid=[];','crypto shortlist live skip');
must('const candidates=broad.rows.slice(0,CONFIG.maxCandidates);let prepared=new Map();','const candidates=entryRows.slice(0,CONFIG.maxCandidates);let prepared=new Map();','noncrypto shortlist live skip');
must('const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);for(const a of analyses)await recordShadowSetup(group,a,scanId,env);','const books=existingBooks,newItems=fillBooks(group,books,analyses);await saveBooks(env,books);for(const a of analyses)await recordShadowSetup(group,a,scanId,env);','reuse durable books');
must('diagnostics:{broadErrors:broad.errors,deepAttempted,skippedUnavailable,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required}','diagnostics:{broadErrors:broad.errors,deepAttempted,skippedUnavailable,liveSymbolsSkipped:[...liveSymbols],tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required}','live skip diagnostics');

// Extend machine-readable knowledge to Metals, with explicit information drivers and uncalibrated status.
const k=JSON.parse(fs.readFileSync(knowledgePath,'utf8'));
k.version='SYMBOL_KNOWLEDGE_V2';
k.generatedAt=new Date().toISOString();
k.symbols.XAUUSD={
  canonicalSymbol:'XAUUSD',legacyPriorKey:null,aliases:['XAUUSD','GOLD'],assetClass:'metal',source:'RUNTIME_KNOWLEDGE',timeframe:'MULTI_TF',priorClassification:'NO_V73_METAL_PRIOR',priorStatus:'KNOWLEDGE_ONLY',families:['MACRO','TREND','MEAN_REVERSION','RELATIVE'],allowedModes:['TREND','MEAN_REVERSION','RELATIVE'],entryMode:'DYNAMIC_REGIME',riskATR:null,priorRR:null,
  contextRequirements:{primary:['DXY / USD regime','US Treasury yields / real-yield proxy','Fed policy expectations','US CPI/PCE/NFP','geopolitical/safe-haven risk'],secondary:['XAG relative strength','session/liquidity','central-bank/gold demand context'],liveRule:'Context can alter direction/quality but cannot replace price structure, freshness or execution authority.'},
  calibration:{status:'PRIOR_ONLY_UNCALIBRATED',reason:'Metal runtime knowledge has not yet passed untouched OOS/walk-forward calibration',sampleSize:0,developmentWinRatePct:null,developmentMeanR:null},
  productionPolicy:{hubScoreIsWinProbability:false,executionRequiresFreshAuthority:true,slPolicy:'STRUCTURE_LIQUIDITY_INVALIDATION_WITH_VOLATILITY_FLOOR',tpPolicy:'FORWARD_STRUCTURE_LIQUIDITY',indicativePlanMayBeWatch:true}
};
k.symbols.XAGUSD={
  canonicalSymbol:'XAGUSD',legacyPriorKey:null,aliases:['XAGUSD','SILVER'],assetClass:'metal',source:'RUNTIME_KNOWLEDGE',timeframe:'MULTI_TF',priorClassification:'NO_V73_METAL_PRIOR',priorStatus:'KNOWLEDGE_ONLY',families:['MACRO','TREND','MEAN_REVERSION','RELATIVE','INDUSTRIAL'],allowedModes:['TREND','MEAN_REVERSION','RELATIVE'],entryMode:'DYNAMIC_REGIME',riskATR:null,priorRR:null,
  contextRequirements:{primary:['DXY / USD regime','US Treasury yields / Fed expectations','XAU relative strength','industrial/risk sentiment'],secondary:['copper/industrial-cycle context when available','session/liquidity','US macro releases'],liveRule:'Context can alter direction/quality but cannot replace price structure, freshness or execution authority.'},
  calibration:{status:'PRIOR_ONLY_UNCALIBRATED',reason:'Metal runtime knowledge has not yet passed untouched OOS/walk-forward calibration',sampleSize:0,developmentWinRatePct:null,developmentMeanR:null},
  productionPolicy:{hubScoreIsWinProbability:false,executionRequiresFreshAuthority:true,slPolicy:'STRUCTURE_LIQUIDITY_INVALIDATION_WITH_VOLATILITY_FLOOR',tpPolicy:'FORWARD_STRUCTURE_LIQUIDITY',indicativePlanMayBeWatch:true}
};
fs.writeFileSync(knowledgePath,JSON.stringify(k,null,2)+'\n');
fs.writeFileSync(worker,s,'utf8');
console.log('Applied V77.13.1 live-order skip and metal knowledge');
