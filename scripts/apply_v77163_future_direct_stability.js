const fs=require('fs');
const p='cloudflare-worker/index.js';let s=fs.readFileSync(p,'utf8');
function must(a,b,l){if(!s.includes(a))throw new Error('Missing '+l);s=s.replace(a,b);}
if(!s.includes('version: "V77.16.2"'))throw new Error('Expected V77.16.2');
s=s.replaceAll('V77.16.2','V77.16.3');
s=s.replace('Trading V77.16.3 Risk-Calibrated Quality Hub','Trading V77.16.3 Stable Direct-Symbol Quality Hub');
must('if(type==="future")x=Math.max(x,mode==="MEAN_REVERSION"?1.25:1.50);','if(type==="future")x=Math.max(x,1.50);','future RR floor');
const helper=`\nasync function recentFutureScanAnalysis(symbol,env,maxAgeMs=75000){\n  try{const snap=await getScanSnapshot("future",env);if(!snap?.scannedAt)return null;const age=Date.now()-Date.parse(snap.scannedAt);if(!Number.isFinite(age)||age<0||age>maxAgeMs)return null;const s=norm(symbol),target=s==="NQ"?"MNQ":s==="ES"?"MES":s,a=(snap.analyses||[]).find(x=>norm(x.symbol)===target);if(!a)return null;return {...a,symbol:s,requestedSymbol:s,source:(a.source||"Massive Futures")+" • fresh scan reuse",freshScanReuse:true,scanAgeSec:Math.round(age/1000),scanId:snap.scanId,dataMode:"CLOSED_5M_BAR_EQUIVALENT",executionReady:false};}catch{return null;}\n}\n`;
must('async function runFutureSymbol(symbol,env){',helper+'async function runFutureSymbol(symbol,env){','future scan reuse helper');
must('  if(type==="future")return runFutureSymbol(s,env);','  if(type==="future"){const recent=await recentFutureScanAnalysis(s,env);if(recent)return recent;try{return await runFutureSymbol(s,env);}catch(e){return {ok:false,status:"DATA_BLOCK",symbol:s,market:"future",reason:"MASSIVE_RATE_OR_DATA_UNAVAILABLE",error:e?.message||String(e),engine:CONFIG.version};}}','future direct stable route');
fs.writeFileSync(p,s);console.log('Applied V77.16.3 Futures direct stability');
