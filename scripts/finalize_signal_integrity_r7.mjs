import fs from 'node:fs';
const ep='cloudflare-worker/engine-v77168.js',hp='cloudflare-worker/hub-v77171.js',cp='cloudflare-worker/claude-reviewer.js';
let e=fs.readFileSync(ep,'utf8'),h=fs.readFileSync(hp,'utf8'),c=fs.readFileSync(cp,'utf8');
const once=(s,a,b)=>s.includes(b)?s:(s.includes(a)?s.replace(a,b):s);

// Currency labels: theoretical USD must still be visibly USD.
e=e.replaceAll('${usd>=0?"+":""}${usd.toFixed(2)}','${usd>=0?"+":""}$${usd.toFixed(2)}');
h=h.replaceAll('${usd>=0?"+":""}${usd.toFixed(2)}','${usd>=0?"+":""}$${usd.toFixed(2)}');

// Manual market scan must refresh only that market's Live lane.
e=once(e,'const run=await runGroup(group,env,"GROUP_MANUAL"),books=await getBooksLive(env);','const run=await runGroup(group,env,"GROUP_MANUAL"),books=await getBooksLive(env,group);');

// Core invariant: MARKET_SIGNAL Telegram notify is allowed only after that signal was persisted to signalActive/newItems.
e=once(e,'async function notifySignalPlans(group,run,env){\n  const plans=(run?.analyses||[]).filter(a=>a?.planned&&["MARKET_SIGNAL","MARKET_PLAN","LIMIT_PLAN"].includes(a.status)).sort((a,b)=>actionableRank(b)-actionableRank(a)).slice(0,2);','async function notifySignalPlans(group,run,env){\n  const persistedSignals=new Set((run?.newItems||[]).filter(p=>p?.signalOnly&&p?.origin==="MARKET_SIGNAL").map(p=>canonicalUserSymbol(p.symbol)));\n  const plans=(run?.analyses||[]).filter(a=>a?.planned&&["MARKET_SIGNAL","MARKET_PLAN","LIMIT_PLAN"].includes(a.status)&&(a.status!=="MARKET_SIGNAL"||persistedSignals.has(canonicalUserSymbol(a.symbol)))).sort((a,b)=>actionableRank(b)-actionableRank(a)).slice(0,2);');
// Do not poison notification dedupe when Telegram delivery fails.
e=once(e,'    await sendText(env,txt,undefined,signalNotifyKeyboard(group,a.symbol)).catch(()=>{});try{await env.TRADING_STATE?.put(key,String(Date.now()),{expirationTtl:1800});}catch{}','    let sent=false;try{await sendText(env,txt,undefined,signalNotifyKeyboard(group,a.symbol));sent=true;}catch{}if(sent)try{await env.TRADING_STATE?.put(key,String(Date.now()),{expirationTtl:1800});}catch{}');

// Hub health should not show Massive red simply because /status omitted the capability flag.
e=once(e,'kv:!!env.TRADING_STATE,twelveData:!!env.TWELVE_DATA_API_KEY,telegram:!!env.TELEGRAM_BOT_TOKEN,','kv:!!env.TRADING_STATE,twelveData:!!env.TWELVE_DATA_API_KEY,massive:!!env.MASSIVE_API_KEY,telegram:!!env.TELEGRAM_BOT_TOKEN,');
// Unknown freshness is not green/fresh.
h=once(h,'fresh=q?.fresh===false?"🔴 STALE":"🟢 FRESH"','fresh=q?.fresh===true?"🟢 FRESH":q?.fresh===false?"🔴 STALE":"⚪ UNKNOWN"');

// Independent Claude reviewer: expose focused deep code and concrete Books lanes.
c=once(c,'function clampText(s,max){s=String(s||"");return s.length>max?s.slice(0,max)+"\\n...[truncated]":s;}','function clampText(s,max){s=String(s||"");return s.length>max?s.slice(0,max)+"\\n...[truncated]":s;}\nfunction focusText(src,needles,radius=900){const s=String(src||""),chunks=[];for(const needle of needles){const at=s.indexOf(needle);if(at<0)continue;chunks.push(s.slice(Math.max(0,at-radius),Math.min(s.length,at+needle.length+radius)));}return clampText([...new Set(chunks)].join("\\n---FOCUS---\\n"),9000);}');
c=once(c,'  const bookView=books&&typeof books==="object"?{keys:Object.keys(books).slice(0,12),size:Array.isArray(books)?books.length:Object.keys(books).length}:null;','  const bookView=books&&typeof books==="object"?Object.fromEntries(Object.entries(books).filter(([k])=>["forex","crypto","metal","index"].includes(k)).map(([g,b])=>[g,{marketActive:(b?.marketActive||[]).length,signalActive:(b?.signalActive||[]).length,limitActive:(b?.limitActive||[]).length,limitPending:(b?.limitPending||[]).length,signals:(b?.signalActive||[]).slice(0,3).map(p=>({symbol:p.symbol,side:p.side,entry:p.entry,sl:p.sl,tp:p.tp,expiresAt:p.expiresAt,source:p.source}))}])):null;');
c=once(c,'  for(const path of CRITICAL_FILES){try{const text=await fetchText(RAW_BASE+path);files.push({path,content:clampText(text,2200)});}catch(e){files.push({path,error:String(e?.message||e)});}}','  for(const path of CRITICAL_FILES){try{const text=await fetchText(RAW_BASE+path),needles=path.endsWith("engine-v77168.js")?["MARKET_SIGNAL","toSignalPos","fillBooks","getBooksLive","lifecycleSignalGroups","notifySignalPlans","signalNotifyKeyboard"]:path.endsWith("hub-v77171.js")?["booksText","MARKET SIGNAL","live:","signal:scan:"]:path.endsWith("index.js")?["ensureDualAiIntervention","scheduled(event","dual-ai/status"]:[];files.push({path,content:needles.length?focusText(text,needles):clampText(text,2200)});}catch(e){files.push({path,error:String(e?.message||e)});}}');
c=c.replace('3) ENTRY QUALITY AND FREQUENCY: inspect Crypto, Forex, Metals and Futures separately.','3) SIGNAL LIVE INTEGRITY: verify MARKET_SIGNAL schema, planned/top-level TP fallback, fillBooks persistence, normalizeBooks preservation, signalActive duplicate suppression, per-market Live refresh, stale quote handling, TP/SL/expiry lifecycle, history and Telegram callback routing. A notified MARKET_SIGNAL must remain in matching Live until explicit TP, SL or expiry; never silently disappear.\n4) ENTRY QUALITY AND FREQUENCY: inspect Crypto, Forex, Metals and Index Cash separately.');
c=c.replace('4) PROP: review per-symbol crypto strategy families','5) PROP: review per-symbol crypto strategy families').replace('5) SYSTEM OPTIMIZATION: identify the smallest high-value changes.','6) SYSTEM OPTIMIZATION: identify the smallest high-value changes.');
c=c.replace('Find conflicts first, then HUB simplification and better market-specific entry discovery','Find signal persistence/lifecycle conflicts first, then HUB simplification and better market-specific entry discovery');

fs.writeFileSync(ep,e);fs.writeFileSync(hp,h);fs.writeFileSync(cp,c);
const checks=[
 [e,'persistedSignals','engine persisted-notify invariant'],[e,'signalActive','engine signal lane'],[e,'lifecycleSignalGroups','engine signal lifecycle'],[e,'sig.planned?.tp2','engine TP fallback'],[e,'q?.fresh===false','engine stale guard'],[e,'massive:!!env.MASSIVE_API_KEY','status Massive flag'],[h,'⚪ UNKNOWN','Hub unknown freshness'],[h,'SIGNAL-ONLY','Hub signal label'],[c,'focusText','Claude focused source'],[c,'signalActive','Claude Books lane'],[c,'SIGNAL LIVE INTEGRITY','Claude integrity prompt']
];
for(const [src,needle,label] of checks)if(!src.includes(needle))throw new Error('FINAL ASSERT missing '+label+' => '+needle);
console.log('Signal Integrity R7 finalizer PASS');
