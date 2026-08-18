const fs = require('fs');
const path = 'cloudflare-worker/index.js';
let s = fs.readFileSync(path, 'utf8');

function mustReplace(from, to, label) {
  if (!s.includes(from)) throw new Error(`Missing patch target: ${label}`);
  s = s.replace(from, to);
}

s = s.replaceAll('V77.7.0', 'V77.7.1');

mustReplace(
`async function tdQuote(symbol,env){`,
`function findNumericField(obj,names){
  if(!obj||typeof obj!=="object")return null;
  for(const [k,v] of Object.entries(obj)){
    if(names.includes(String(k).toLowerCase())){const n=num(v);if(n!==null)return n;}
    if(v&&typeof v==="object"){const n=findNumericField(v,names);if(n!==null)return n;}
  }
  return null;
}
async function tdQuotaStatus(env){
  if(!env.TWELVE_DATA_API_KEY)return {left:0,used:null,error:"TWELVE_DATA_API_KEY missing"};
  const q=new URLSearchParams({apikey:env.TWELVE_DATA_API_KEY});
  const r=await fetchTimeout(\`https://api.twelvedata.com/api_usage?\${q}\`);
  const payload=await r.json().catch(()=>null);
  let left=num(r.headers.get("api-credits-left")),used=num(r.headers.get("api-credits-used"));
  if(left===null)left=findNumericField(payload,["api_credits_left","credits_left","remaining_credits","credits_remaining","remaining"]);
  if(used===null)used=findNumericField(payload,["api_credits_used","credits_used","used_credits","used"]);
  if(left===null&&r.status===429)left=0;
  if(left!==null)memory.tdCreditsLeft=left;
  return {left,used,status:r.status,payload};
}
function tdFullScanCost(group){return group==="forex"?43:group==="crypto"?45:group==="metal"?12:0;}
function tdRetryAfterSec(){return Math.max(3,62-(Math.floor(Date.now()/1000)%60));}
async function ensureTdBudget(group,env){
  const required=tdFullScanCost(group),q=await tdQuotaStatus(env);
  if(q.left!==null&&q.left<required)return {ok:false,required,left:q.left,retryAfterSec:tdRetryAfterSec()};
  return {ok:true,required,left:q.left};
}

async function tdQuote(symbol,env){`,
'quota helper insertion'
);

mustReplace(
`    const enrich=await cryptoRotation(env); let map=new Map(); try{map=await tdBatchCandles(enrich,"1h",env,60);}catch{}
    for(const sym of enrich){const c=map.get(sym),T=tf(c||[]);if(!T.ready)continue;const i=rows.findIndex(r=>r.symbol===sym),score=Math.abs((T.close-(T.ema20??T.close))/(T.atr14||1));if(i>=0)rows[i].strength+=score;else rows.push({symbol:sym,quote:{source:"Twelve Data H1",price:T.close,fresh:true},strength:score});}`,
`    const rotation=await cryptoRotation(env),missing=symbols.filter(sym=>!bulk.get(sym)?.price),enrich=[...new Set([...missing,...rotation])].slice(0,CONFIG.cryptoTdBroadPerScan); let map=new Map(); try{map=await tdBatchCandles(enrich,"1h",env,60);}catch{}
    for(const sym of enrich){const c=map.get(sym),T=tf(c||[]);if(!T.ready)continue;const i=rows.findIndex(r=>r.symbol===sym),score=Math.abs((T.close-(T.ema20??T.close))/(T.atr14||1));if(i>=0)rows[i].strength+=score;else{rows.push({symbol:sym,quote:{source:"Twelve Data H1",price:T.close,fresh:true},strength:score});const ei=errors.findIndex(e=>e.symbol===sym);if(ei>=0)errors.splice(ei,1);}}`,
'crypto missing exact fallback'
);

mustReplace(
`async function runGroup(group,env){
  if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group};const started=Date.now();
  try{const broad=await broadScan(group,env);const candidates=broad.rows.slice(0,CONFIG.maxCandidates),candidateSymbols=candidates.map(c=>c.symbol);let prepared=new Map();try{prepared=await prepareDeepCandles(candidateSymbols,env);}catch{}const analyses=[];for(const c of candidates){if(Date.now()-started>CONFIG.scanDeadlineMs)break;try{analyses.push(await deepAnalyze(c.symbol,env,prepared.get(c.symbol)||null));}catch(e){analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"DEEP_ERROR",error:e?.message||String(e)});}}
    const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);const out={ok:true,version:CONFIG.version,group,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:candidates.length,deepOk:analyses.length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,tdCreditsLeft:memory.tdCreditsLeft},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;
  }finally{await releaseLock(env);}
}`,
`async function runGroup(group,env){
  if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group};const started=Date.now();
  try{
    const budget=await ensureTdBudget(group,env);
    if(!budget.ok){const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;}
    const broad=await broadScan(group,env);const candidates=broad.rows.slice(0,CONFIG.maxCandidates),candidateSymbols=candidates.map(c=>c.symbol);let prepared=new Map();try{prepared=await prepareDeepCandles(candidateSymbols,env);}catch{}const analyses=[];for(const c of candidates){if(Date.now()-started>CONFIG.scanDeadlineMs)break;try{analyses.push(await deepAnalyze(c.symbol,env,prepared.get(c.symbol)||null));}catch(e){analyses.push({ok:false,status:"DATA_BLOCK",symbol:c.symbol,reason:"DEEP_ERROR",error:e?.message||String(e)});}}
    const books=await getBooks(env),newItems=fillBooks(group,books,analyses);await saveBooks(env,books);const out={ok:true,version:CONFIG.version,group,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:candidates.length,deepOk:analyses.length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;
  }finally{await releaseLock(env);}
}`,
'quota guarded runGroup'
);

mustReplace(
`  if(run){L.push(\`🔍 Quét: \${run.requested} | Phân tích: \${run.deepOk} | Mới: \${run.newCount}\`,\`🧪 Data: \${run.broadOk}/\${run.requested} broad OK | deep \${run.deepOk}/\${run.deepRequested}\`);`,
`  if(run){if(run.status==="RATE_BUDGET_WAIT"){L.push(\`⏱ Twelve Data đang hồi quota. Còn \${run.diagnostics?.tdCreditsLeft??"?"} credit, cần \${run.diagnostics?.tdCreditsRequired??"?"}. Hãy thử lại sau khoảng \${run.retryAfterSec??60} giây.\`);return L.join("\\n");}L.push(\`🔍 Quét: \${run.requested} | Phân tích: \${run.deepOk} | Mới: \${run.newCount}\`,\`🧪 Data: \${run.broadOk}/\${run.requested} broad OK | deep \${run.deepOk}/\${run.deepRequested}\`);`,
'friendly quota wait UI'
);

fs.writeFileSync(path, s, 'utf8');
console.log('Applied V77.7.1 Twelve Data quota guard.');
