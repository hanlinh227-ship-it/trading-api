import fs from 'node:fs';
const ep='cloudflare-worker/engine-v77168.js',hp='cloudflare-worker/hub-v77171.js',dp='cloudflare-worker/dual-ai-intervention.js',vp='.github/workflows/validate-cloudflare-v77.yml';
let e=fs.readFileSync(ep,'utf8'),h=fs.readFileSync(hp,'utf8'),d=fs.readFileSync(dp,'utf8'),v=fs.readFileSync(vp,'utf8');
const must=(src,old,neu,label)=>{if(!src.includes(old))throw new Error('missing '+label);return src.replace(old,neu);};
e=must(e,'version: "V77.16.19",\n  service: "Trading V77.16.19 Signal Live Sync R6",','version: "V77.16.20",\n  service: "Trading V77.16.20 Signal Lifecycle Guard R7",','engine version');
const oldSig='function toSignalPos(sig,discoveredBy="SCAN",group="forex"){const tp=Number.isFinite(Number(sig.tp2))?Number(sig.tp2):Number(sig.tp1),ttl=group==="forex"?12:8;return {id:`signal-${sig.symbol}-${Date.now()}`,symbol:sig.symbol,side:sig.side,entry:Number(sig.entry??sig.planned?.entry),sl:Number(sig.sl??sig.planned?.sl),tp,tp1:Number(sig.tp1??sig.planned?.tp1),tp2:Number(sig.tp2??sig.planned?.tp2),targetRR:Number(sig.targetRR??sig.planned?.targetRR),origin:"MARKET_SIGNAL",discoveredBy,status:"ACTIVE",openedAt:Date.now(),createdAt:Date.now(),expiresAt:Date.now()+ttl*3600000,engineOpened:sig.engine,engine:sig.engine,source:sig.analysisQuote?.source||sig.quote?.source||sig.source,executionVerified:false,executionAuthority:"SIGNAL_ONLY",signalOnly:true,riskUsd:CONFIG.defaultRiskUsd};}';
const newSig='function toSignalPos(sig,discoveredBy="SCAN",group="forex"){const entry=Number(sig.entry??sig.planned?.entry),sl=Number(sig.sl??sig.planned?.sl),tp1=Number(sig.tp1??sig.planned?.tp1),tp2=Number(sig.tp2??sig.planned?.tp2),tp=Number.isFinite(tp2)&&tp2>0?tp2:tp1,ttl=group==="forex"?12:8;if(![entry,sl,tp].every(x=>Number.isFinite(x)&&x>0))return null;return {id:`signal-${sig.symbol}-${Date.now()}`,symbol:sig.symbol,side:sig.side,entry,sl,tp,tp1,tp2,targetRR:Number(sig.targetRR??sig.planned?.targetRR),origin:"MARKET_SIGNAL",discoveredBy,status:"ACTIVE",openedAt:Date.now(),createdAt:Date.now(),expiresAt:Date.now()+ttl*3600000,engineOpened:sig.engine,engine:sig.engine,source:sig.analysisQuote?.source||sig.quote?.source||sig.source,executionVerified:false,executionAuthority:"SIGNAL_ONLY",signalOnly:true,riskUsd:CONFIG.defaultRiskUsd};}';
e=must(e,oldSig,newSig,'signal schema');
e=e.replace('const p=toSignalPos(a,trigger,group);b.signalActive.push(p);newItems.push(p);','const p=toSignalPos(a,trigger,group);if(p){b.signalActive.push(p);newItems.push(p);}');
const marker='async function lifecycle(env){\n  const books=await getBooks(env),b=books.crypto;let changed=false,pending=[];';
const signalLife=`async function lifecycleSignalBooks(env,books){let changed=false;for(const g of ["forex","metal","index"]){const b=books[g],keep=[];for(const p of b.signalActive||[]){if(p.expiresAt&&Date.now()>Number(p.expiresAt)){changed=true;await appendOrderHistory(env,{event:"SIGNAL_EXPIRED",group:g,position:p});continue;}try{const q=await liveBookQuote(g,p,env),px=Number(q?.price);if(!(px>0)){keep.push(p);continue;}const hitTP=p.side==="LONG"?px>=Number(p.tp):px<=Number(p.tp),hitSL=p.side==="LONG"?px<=Number(p.sl):px>=Number(p.sl);if(hitTP||hitSL){changed=true;await appendOrderHistory(env,{event:hitTP?"SIGNAL_TP":"SIGNAL_SL",group:g,position:p,closePrice:px});await sendText(env,signalEventText(hitTP?"TP":"SL",p,{group:g,closePrice:px}),undefined,signalNotifyKeyboard(g,p.symbol)).catch(()=>{});}else keep.push(p);}catch{keep.push(p);}}b.signalActive=keep;}return changed;}\n`;
if(!e.includes('async function lifecycleSignalBooks'))e=must(e,marker,signalLife+marker,'signal lifecycle insertion');
e=e.replace('  if(changed)await saveBooks(env,books);\n}','  if(await lifecycleSignalBooks(env,books))changed=true;\n  if(changed)await saveBooks(env,books);\n}',1);
// scoped live should never use Twelve Data index aliases without native identity; reuse canonical index quote route if present.
e=e.replace('if(g==="index")return await tdQuote(p.symbol,env);','if(g==="index")return await currentQuote(p.symbol,env);');
// Fix stale legacy wording and make event text explicit for signal-only closure.
e=e.replace('"🔄 Mở 📚 Live Orders để refresh P/L % + USD"','"🔄 Mở 📚 Live đúng thị trường để refresh giá/P&L"');
h=must(h,'const VERSION="V77.18.41",UI_REV="HUB-R9-SIGNAL-LIVE-SYNC",SERVICE="Trading V77.18.41 • Signal Live Sync";','const VERSION="V77.18.42",UI_REV="HUB-R10-LIFECYCLE-GUARD",SERVICE="Trading V77.18.42 • Signal Lifecycle Guard";','hub version');
// restore $ sign for theoretical USD display and label estimated values clearly.
h=h.replace('`${usd>=0?"+":""}${usd.toFixed(2)}`','`$${usd>=0?"+":""}${usd.toFixed(2)}`');
// Claude: compact bug-hunt only, no autonomous source write/deploy authority.
d=d.replace('const REVIEW_REV="MARKET_BALANCE_R5_BUDGET";','const REVIEW_REV="BUG_HUNT_R6_STATE_LIFECYCLE";');
d=d.replace('const cut=(s,n=1600)=>String(s||"").slice(0,n);','const cut=(s,n=1400)=>String(s||"").slice(0,n);');
d=d.replace('max_tokens:1400','max_tokens:950');
d=d.replace('Perform MARKET_BALANCE_R5_BUDGET first. Spend tokens only on high-impact duplicated gates, MARKET-vs-LIMIT imbalance, Forex opportunity suppression, Hyro A/B market routing, and deployment/runtime consistency.','Perform BUG_HUNT_R6_STATE_LIFECYCLE first. Spend tokens only on concrete bugs: state persistence, MARKET_SIGNAL schema, TP/SL lifecycle, stale/incorrect quote routing, duplicate suppression, scoped Telegram callbacks, Hub rendering, prop runtime state, and deployment/runtime consistency. Do not spend tokens on cosmetic prose.');
d=d.replace('lastAction:"MARKET_BALANCE_R5_BUDGET"','lastAction:"BUG_HUNT_R6_STATE_LIFECYCLE"');
d=d.replace('🧠 CLAUDE • MARKET BALANCE R5','🧠 CLAUDE • BUG HUNT R6');
// Canonical validation locks.
v=v.replaceAll('V77.16.19','V77.16.20').replaceAll("'V77.18.41','HUB-R9-SIGNAL-LIVE-SYNC'","'V77.18.42','HUB-R10-LIFECYCLE-GUARD'");
v=v.replace("'signalActive','MARKET SIGNAL','SIGNAL_ONLY'","'signalActive','MARKET SIGNAL','SIGNAL_ONLY','lifecycleSignalBooks','SIGNAL_EXPIRED','SIGNAL_TP','SIGNAL_SL'");
v=v.replaceAll('V77.18.41 Signal Live Sync validation PASS','V77.18.42 Signal Lifecycle Guard validation PASS');
fs.writeFileSync(ep,e);fs.writeFileSync(hp,h);fs.writeFileSync(dp,d);fs.writeFileSync(vp,v);console.log('V77.18.42 bug-hunt R6 migration complete');
