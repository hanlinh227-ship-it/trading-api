const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing start '+label);const b=s.indexOf(end,a+start.length);if(b<0)throw new Error('Missing end '+label);s=s.slice(0,a)+repl+s.slice(b);}

s=s.replaceAll('V77.11.2','V77.12.0');
s=s.replaceAll('Trading V77.12.0 Dynamic Regime Entry Hub','Trading V77.12.0 Fresh Scan Persistent Order Hub');
mustReplace('cryptoBroadCache: "v779:crypto_broad_cache",','cryptoBroadCache: "v779:crypto_broad_cache",\n    scanPrefix: "v7712:scan:",\n    orderHistory: "v7712:order_history",','state keys');

const stateBlock=[
'function emptyGroup(){return {marketActive:[],limitActive:[],limitPending:[],watch:[]};}',
'function emptyBooks(){return {forex:emptyGroup(),crypto:emptyGroup(),metal:emptyGroup(),updatedAt:Date.now()};}',
'function validExecutablePosition(p,group){',
'  if(!p||typeof p!=="object"||!GROUPS[group]?.includes(canonicalUserSymbol(p.symbol)))return false;',
'  if(!["LONG","SHORT"].includes(p.side))return false;',
'  if(![p.entry,p.sl,p.tp].every(v=>Number.isFinite(Number(v))&&Number(v)>0))return false;',
'  if(group==="crypto")return true;',
'  return p.executionVerified===true||!!p.brokerTicket||p.executionAuthority==="MT5";',
'}',
'function normalizeBooks(v){const b=emptyBooks();if(!v||typeof v!=="object")return b;for(const g of Object.keys(GROUPS)){const src=v?.[g]||{};b[g].marketActive=Array.isArray(src.marketActive)?src.marketActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxMarketActive):[];b[g].limitActive=Array.isArray(src.limitActive)?src.limitActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxLimitActive):[];b[g].limitPending=Array.isArray(src.limitPending)?src.limitPending.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxPendingLimit):[];b[g].watch=[];}b.updatedAt=v.updatedAt||Date.now();return b;}',
'async function getBooks(env){try{return normalizeBooks(await env.TRADING_STATE.get(CONFIG.keys.books,"json"));}catch{return emptyBooks();}}',
'async function saveBooks(env,b){b.updatedAt=Date.now();for(const g of Object.keys(GROUPS))b[g].watch=[];await env.TRADING_STATE.put(CONFIG.keys.books,JSON.stringify(b));}',
'async function saveScanSnapshot(group,run,env){try{await env.TRADING_STATE.put(CONFIG.keys.scanPrefix+group,JSON.stringify(run),{expirationTtl:900});}catch{}}',
'async function getScanSnapshot(group,env){try{return await env.TRADING_STATE.get(CONFIG.keys.scanPrefix+group,"json");}catch{return null;}}',
'async function appendOrderHistory(env,event){try{const old=await env.TRADING_STATE.get(CONFIG.keys.orderHistory,"json"),rows=Array.isArray(old?.rows)?old.rows:[];rows.unshift({...event,recordedAt:Date.now(),engine:CONFIG.version});await env.TRADING_STATE.put(CONFIG.keys.orderHistory,JSON.stringify({rows:rows.slice(0,250),updatedAt:Date.now()}));}catch{}}',
'function sideText(x){return x==="LONG"?"BUY":x==="SHORT"?"SELL":"NEUTRAL";}',
'function duplicate(book,sym){return [...book.marketActive,...book.limitActive,...book.limitPending].some(x=>x.symbol===sym);}',
'function toPos(sig){return {id:sig.symbol+"-"+Date.now(),symbol:sig.symbol,side:sig.side,entry:sig.entry,sl:sig.sl,tp:sig.targetRR===2?sig.tp2:sig.tp1,tp1:sig.tp1,tp2:sig.tp2,targetRR:sig.targetRR,origin:sig.action,status:"ACTIVE",openedAt:Date.now(),engineOpened:sig.engine,engine:sig.engine,source:sig.quote?.source,executionVerified:true,executionAuthority:sig.quote?.source||"CANONICAL_CRYPTO"};}',
'function fillBooks(group,books,analyses){const b=books[group],newItems=[];for(const a of analyses){if(group!=="crypto")continue;if(a.status==="MARKET"&&!duplicate(b,a.symbol)&&b.marketActive.length<CONFIG.maxMarketActive){const p=toPos(a);b.marketActive.push(p);newItems.push(p);}if(a.status==="LIMIT"&&!duplicate(b,a.symbol)&&b.limitPending.length<CONFIG.maxPendingLimit&&(b.limitActive.length+b.limitPending.length)<CONFIG.maxLimitActive){const p={...toPos(a),status:"PENDING",expiresAt:Date.now()+CONFIG.pendingLimitExpiryMinutes*60000};b.limitPending.push(p);newItems.push(p);}}b.watch=[];return newItems;}',
'function freshWatchFromRun(run){return (run?.analyses||[]).filter(x=>x?.status==="WATCH").sort((a,b)=>(Number(b.score)||0)-(Number(a.score)||0)).slice(0,CONFIG.maxWatch);}',
''
].join('\n');
replaceRange('function emptyGroup(){','async function acquireLock(',stateBlock,'persistent order state');

mustReplace('if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group};','if(!GROUPS[group])throw new Error("invalid group");if(!(await acquireLock(env)))return {ok:false,status:"BUSY",group,version:CONFIG.version,scanId:group+"-busy-"+Date.now(),scannedAt:new Date().toISOString(),analyses:[]};','busy response');
mustReplace('const started=Date.now();\n  try{','const started=Date.now(),scanId=group+"-"+started+"-"+Math.random().toString(36).slice(2,8),scannedAt=new Date(started).toISOString();\n  try{','scan identity');
mustReplace('const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;','const out={ok:true,version:CONFIG.version,status:"RATE_BUDGET_WAIT",group,scanId,scannedAt,requested:GROUPS[group].length,broadOk:0,fresh:0,deepRequested:0,deepOk:0,newCount:0,analyses:[],retryAfterSec:budget.retryAfterSec,diagnostics:{broadErrors:[],tdCreditsLeft:budget.left,tdCreditsRequired:budget.required},elapsedMs:Date.now()-started};await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));await saveScanSnapshot(group,out,env);return out;','quota snapshot');
mustReplace('const out={ok:true,version:CONFIG.version,group,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:Math.min(CONFIG.maxCandidates,broad.rows.length),deepOk:analyses.filter(a=>a.ok!==false).length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,deepAttempted,skippedUnavailable,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};\n    await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));return out;','const out={ok:true,version:CONFIG.version,group,scanId,scannedAt,requested:broad.requested,broadOk:broad.rows.length,fresh:broad.rows.length,deepRequested:Math.min(CONFIG.maxCandidates,broad.rows.length),deepOk:analyses.filter(a=>a.ok!==false).length,newCount:newItems.length,analyses,diagnostics:{broadErrors:broad.errors,deepAttempted,skippedUnavailable,tdCreditsLeft:memory.tdCreditsLeft,tdCreditsAtStart:budget.left,tdCreditsPlanned:budget.required},elapsedMs:Date.now()-started};\n    await env.TRADING_STATE.put(CONFIG.keys.lastRun,JSON.stringify(out));await saveScanSnapshot(group,out,env);return out;','success snapshot');

const keyboardBlock=[
'function groupKeyboard(group,run){const rows=baseKeyboard().inline_keyboard,pending=freshWatchFromRun(run).filter(w=>w.reason==="NEWS_CONTEXT_REQUIRED").slice(0,3);if(pending.length)rows.unshift(pending.map(w=>({text:"✅ Tin OK "+w.symbol,callback_data:"news:"+group+":"+w.symbol})));return {inline_keyboard:rows};}',
'function hubKeyboard(h){const rows=baseKeyboard().inline_keyboard,p=[];for(const [g,r] of Object.entries(h?.runs||{}))for(const w of freshWatchFromRun(r))if(w.reason==="NEWS_CONTEXT_REQUIRED"&&p.length<3)p.push({text:"✅ Tin OK "+w.symbol,callback_data:"news:"+g+":"+w.symbol});if(p.length)rows.unshift(p);return {inline_keyboard:rows};}',
''
].join('\n');
replaceRange('function groupKeyboard(','function groupTitle(',keyboardBlock,'fresh keyboards');

const uiBlock=[
'function summary(group,books,run=null){',
'  const b=books[group],watch=freshWatchFromRun(run),L=[groupTitle(group)];',
'  if(run?.scannedAt)L.push("🕒 Quét mới: "+run.scannedAt);',
'  L.push("","🟢 MARKET ĐANG CHẠY "+b.marketActive.length+"/"+CONFIG.maxMarketActive);if(b.marketActive.length)b.marketActive.forEach((p,i)=>L.push((i+1)+". "+posLine(p)));else L.push("Trống");',
'  L.push("","🔵 LIMIT ĐÃ KHỚP "+b.limitActive.length+"/"+CONFIG.maxLimitActive);if(b.limitActive.length)b.limitActive.forEach((p,i)=>L.push((i+1)+". "+posLine(p)));else L.push("Trống");',
'  L.push("","🟡 LIMIT CHỜ "+b.limitPending.length+"/"+CONFIG.maxPendingLimit);if(b.limitPending.length)b.limitPending.forEach((p,i)=>L.push((i+1)+". "+posLine(p)));else L.push("Trống");',
'  L.push("","👀 SETUP TỪ LẦN QUÉT NÀY "+watch.length+"/"+CONFIG.maxWatch);if(watch.length)watch.forEach((w,i)=>L.push((i+1)+". "+watchLine(w)));else L.push("Không có setup mới đạt chuẩn.");',
'  if(run?.status==="RATE_BUDGET_WAIT"){L.push("⏱ Không dùng WATCH cũ. Chờ quota ~"+(run.retryAfterSec??60)+"s.");return L.join("\\n");}',
'  if(run?.status==="BUSY"){L.push("⏳ Một lượt quét khác đang chạy. Không hiển thị setup cũ thay cho kết quả mới.");return L.join("\\n");}',
'  if(run)L.push("🔍 Coverage "+run.broadOk+"/"+run.requested+" • Deep "+run.deepOk+"/"+run.deepRequested+" • Lệnh mới "+run.newCount,"🆔 Scan "+run.scanId);',
'  return L.join("\\n");',
'}',
'async function sendGroup(group,env,chatId){await sendText(env,"⏳ Đang quét MỚI "+group.toUpperCase()+"...",chatId);const run=await runGroup(group,env),books=await getBooks(env);return sendText(env,summary(group,books,run),chatId,groupKeyboard(group,run));}',
'function hubRank(a){const base=Number(a.score)||0;if(a.status==="MARKET")return 200+base;if(a.status==="LIMIT")return 190+base;if(a.reason==="EXECUTION_QUOTE_REQUIRED"||a.reason==="FINAL_QUOTE_REQUIRED")return 170+base;if(a.reason==="NEWS_CONTEXT_REQUIRED")return 160+base;if(a.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")return 120+base;if(a.reason==="M15_LOCATION_REQUIRED")return 90+base;return base;}',
'async function runHub(env){const t=Date.now(),runs={};for(const g of ["crypto","forex","metal"])runs[g]=await runGroup(g,env);const top=Object.entries(runs).flatMap(([group,r])=>(r.analyses||[]).map(a=>({...a,group,scanId:r.scanId,scannedAt:r.scannedAt}))).sort((a,b)=>hubRank(b)-hubRank(a)).slice(0,7);return {ok:true,version:CONFIG.version,hubScanId:"hub-"+t+"-"+Math.random().toString(36).slice(2,8),scannedAt:new Date(t).toISOString(),runs,top};}',
'function hubSummary(h){const L=["🧭 TRADING HUB "+CONFIG.version,"🕒 QUÉT MỚI: "+h.scannedAt,"🆔 "+h.hubScanId,"","🔥 TOP SETUPS CỦA LẦN QUÉT NÀY"];if(!h.top.length)L.push("Không có setup mới đạt chuẩn lúc này.");h.top.slice(0,5).forEach((a,i)=>{let line=(i+1)+". "+a.symbol+" "+sideText(a.side)+" • "+stageText(a)+" • "+(Number(a.score)||0)+"/100";if(a.method?.profile||a.method?.families?.length)line+="\\n   ↳ Profile: "+(a.method?.profile||a.method?.families?.[0]);if(a.method?.activeMode)line+="\\n   ↳ Route: "+a.method.activeMode;if(a.planned){const tag=a.planned.indicative?"Entry tham khảo":"Kế hoạch";line+="\\n   ↳ "+tag+": E~"+fmtPx(a.planned.entry)+" • SL~"+fmtPx(a.planned.sl)+" • TP~"+fmtPx(a.planned.tp2||a.planned.tp1)+" • RR~"+Number(a.planned.targetRR||0).toFixed(2);}line+="\\n   ↳ "+(a.status==="WATCH"?reasonText(a.reason):"Đủ gate execution");L.push(line);});L.push("","Điểm Hub = độ hoàn thiện setup, KHÔNG phải xác suất thắng.");for(const g of ["forex","crypto","metal"]){const r=h.runs[g];L.push(groupTitle(g)+" • "+(r.status==="RATE_BUDGET_WAIT"?"đợi quota — không dùng setup cũ":r.status==="BUSY"?"BUSY — không dùng setup cũ":r.broadOk+"/"+r.requested+" • deep "+r.deepOk+"/"+r.deepRequested));}return L.join("\\n");}',
'async function sendHub(env,chatId){await sendText(env,"⏳ HUB đang QUÉT MỚI Crypto + Forex + Metal...",chatId);const h=await runHub(env);return sendText(env,hubSummary(h),chatId,hubKeyboard(h));}',
'function booksSummary(books){const L=["📚 LIVE ORDERS — LƯU BỀN QUA UPDATE BOT"];for(const g of ["forex","crypto","metal"]){const b=books[g];L.push(groupTitle(g)+" • MARKET "+b.marketActive.length+" • LIMIT ACTIVE "+b.limitActive.length+" • LIMIT CHỜ "+b.limitPending.length);}L.push("WATCH/SETUP không nằm trong Books; mỗi lần bấm Hub sẽ quét mới.");return L.join("\\n");}',
''
].join('\n');
replaceRange('function summary(group,books,run=null){','async function lifecycle(env){',uiBlock,'fresh UI');

mustReplace('if(p.expiresAt&&Date.now()>p.expiresAt){changed=true;continue;}','if(p.expiresAt&&Date.now()>p.expiresAt){changed=true;await appendOrderHistory(env,{event:"LIMIT_EXPIRED",group:"crypto",position:p});continue;}','expiry history');
mustReplace('p.status="ACTIVE";p.openedAt=Date.now();b.limitActive.push(p);changed=true;await sendText(env,`🔵 LIMIT ĐÃ KHỚP\\n${p.symbol} ${sideText(p.side)}\\nEntry: ${p.entry}`).catch(()=>{});','p.status="ACTIVE";p.openedAt=Date.now();b.limitActive.push(p);changed=true;await appendOrderHistory(env,{event:"LIMIT_FILLED",group:"crypto",position:p,price:px});await sendText(env,"🔵 LIMIT ĐÃ KHỚP\\n"+p.symbol+" "+sideText(p.side)+"\\nEntry: "+p.entry).catch(()=>{});','fill history');
mustReplace('if(hitTP||hitSL){changed=true;await sendText(env,`${hitTP?"✅ TAKE PROFIT":"❌ STOP LOSS"}\\n${p.symbol} ${sideText(p.side)}\\n${hitTP?"TP":"SL"}: ${px}`).catch(()=>{});}else keep.push(p);','if(hitTP||hitSL){changed=true;await appendOrderHistory(env,{event:hitTP?"TP":"SL",group:"crypto",position:p,closePrice:px});await sendText(env,(hitTP?"✅ TAKE PROFIT":"❌ STOP LOSS")+"\\n"+p.symbol+" "+sideText(p.side)+"\\n"+(hitTP?"TP":"SL")+": "+px).catch(()=>{});}else keep.push(p);','close history');

mustReplace('if(p==="/books")return json(await getBooks(env));','if(p==="/books"||p==="/orders")return json(await getBooks(env));\n      if(p==="/latest-scan"){const g=u.searchParams.get("group");if(!GROUPS[g])return json({ok:false,error:"invalid group"},400);return json({ok:true,group:g,snapshot:await getScanSnapshot(g,env)});}','scan endpoints');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.12.0 fresh-scan persistent-order architecture');
