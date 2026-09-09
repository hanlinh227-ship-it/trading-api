from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text();a=A.read_text();g=G.read_text()

def rep(text,old,new,label,count=1):
    if old not in text: raise SystemExit('missing '+label)
    return text.replace(old,new,count)

w=rep(w,'SIGNALHUB-V3-GATEWAY-3.22.0','SIGNALHUB-V3-GATEWAY-3.22.1','worker version')
a=rep(a,'private static final String APP_VERSION="3.22.0";','private static final String APP_VERSION="3.22.1";','app version')
g=rep(g,'versionCode 29','versionCode 30','version code')
g=rep(g,"versionName '3.22.0'","versionName '3.22.1'",'version name')
w=w.replace("versionCode: 29,\n  versionName: '3.22.0',","versionCode: 30,\n  versionName: '3.22.1',",1)
w=w.replace("title: 'SignalHub 3.22 Universe Watch + Refined Market Read'","title: 'SignalHub 3.22.1 Universe Watch + Resilient Read'",1)
w=w.replace("artifactName: 'SignalHub-Android-v3.22.0-Universe-Watch-Refined-Read'","artifactName: 'SignalHub-Android-v3.22.1-Universe-Watch-Resilient-Read'",1)

# Insert a versioned, freshness-bounded Watch TF cache and an OKX history endpoint fallback.
needle='function buildWatchIdealReference(t,style,stats){'
if needle not in w: raise SystemExit('watch ideal builder missing')
resilience=r'''const WATCH_TF_CACHE_SCHEMA='V3221_WATCH_TF_STATS_1';
function watchTfTtlMs(interval){return interval==='5m'?15*60*1000:interval==='15m'?45*60*1000:interval==='1h'?2*60*60*1000:interval==='4h'?8*60*60*1000:36*60*60*1000;}
function watchTfCacheKey(symbol,interval){return `v3221:watch:tf:${WATCH_TF_CACHE_SCHEMA}:${canonical(symbol)}:${interval}`;}
async function okxHistoryCandlesV3221(symbol,interval,limit=100){
  const inst=symbol.replace(/USDT$/,'-USDT-SWAP'),bar={"5m":'5m',"15m":'15m',"1h":'1H',"4h":'4H',"1d":'1D'}[interval],raw=await fetchJson(`https://www.okx.com/api/v5/market/history-candles?instId=${encodeURIComponent(inst)}&bar=${bar}&limit=${Math.min(100,limit)}`,{},9000);
  if(String(raw?.code||'0')!=='0')throw new Error('OKX_HISTORY_CANDLES_'+raw?.code);
  const rows=(raw?.data||[]).map(x=>({t:Number(x[0]),o:Number(x[1]),h:Number(x[2]),l:Number(x[3]),c:Number(x[4]),v:Number(x[5])})).filter(x=>Number.isFinite(x.c)).sort((a,b)=>a.t-b.t);if(rows.length<55)throw new Error('OKX_HISTORY_CANDLES_SHORT');return rows;
}
async function readWatchTfCacheV3221(env,symbol,interval){
  if(!env?.SIGNALS_KV)return null;try{const raw=await env.SIGNALS_KV.get(watchTfCacheKey(symbol,interval));if(!raw)return null;const x=JSON.parse(raw),ageMs=Math.max(0,Date.now()-Number(x.fetchedAt||0));if(x.schema!==WATCH_TF_CACHE_SCHEMA||x.interval!==interval||canonical(x.symbol)!==canonical(symbol)||!x.stats||ageMs>watchTfTtlMs(interval))return null;return {...x,ageMs};}catch{return null;}
}
async function putWatchTfCacheV3221(env,symbol,interval,stats,provider){
  if(!env?.SIGNALS_KV||!stats)return;try{await env.SIGNALS_KV.put(watchTfCacheKey(symbol,interval),JSON.stringify({schema:WATCH_TF_CACHE_SCHEMA,symbol:canonical(symbol),interval,stats,provider,fetchedAt:Date.now()}),{expirationTtl:172800});}catch{}
}
async function watchTfStatsV3221(t,interval,env){
  const symbol=canonical(t?.symbol),preferred=String(t?.exchange||t?.venue||t?.provider||'').toUpperCase(),order=[preferred,'OKX','BYBIT','BINANCE'].filter((x,i,a)=>['OKX','BYBIT','BINANCE'].includes(x)&&a.indexOf(x)===i),errors=[];
  for(const provider of order){
    const fns=provider==='OKX'?[okxCandles,okxHistoryCandlesV3221]:provider==='BYBIT'?[bybitCandles]:[binanceCandles];
    for(const fn of fns){try{const rows=await fn(symbol,interval);const stats=tfStats(rows);if(!stats)throw new Error('TF_STATS_INVALID');await putWatchTfCacheV3221(env,symbol,interval,stats,provider);return {stats,provider,mode:'FRESH_CANDLES',ageMs:0,errors};}catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}}
  }
  const cached=await readWatchTfCacheV3221(env,symbol,interval);if(cached)return {stats:cached.stats,provider:cached.provider||preferred||null,mode:'RECENT_VALID_TF_CACHE',ageMs:cached.ageMs,errors};
  return {stats:null,provider:preferred||null,mode:'UNAVAILABLE',ageMs:null,errors};
}
async function watchStatsBundleV3221(t,style,env){
  const frames=intervalMap[style],items=[];for(const frame of frames){items.push(await watchTfStatsV3221(t,frame,env));if(items.at(-1)?.stats==null)break;await sleep(65);}
  if(items.length!==frames.length||items.some(x=>!x.stats))return {ok:false,stats:null,frames:items,mode:'UNAVAILABLE',ageMs:null};
  const cached=items.some(x=>x.mode!=='FRESH_CANDLES'),ageMs=Math.max(...items.map(x=>Number(x.ageMs||0)));return {ok:true,stats:items.map(x=>x.stats),frames:items,mode:cached?'RECENT_VALID_TF_CACHE':'FRESH_CANDLES',ageMs};
}
'''
w=w.replace(needle,resilience+needle,1)

# Replace ideal analyzer so each timeframe is resolved independently and can use only recent validated cached TF stats.
old="async function analyzeWatchIdealReference(t,style){\n  try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildWatchIdealReference(t,style,stats);}catch{return null;}\n}"
new=r'''async function analyzeWatchIdealReference(t,style,env){
  try{const bundle=await watchStatsBundleV3221(t,style,env);if(!bundle.ok)return null;const ideal=buildWatchIdealReference(t,style,bundle.stats);if(!ideal)return null;ideal.watchDataMode=bundle.mode;ideal.watchDataAgeMs=bundle.ageMs;ideal.watchTimeframes=intervalMap[style].map((frame,i)=>({frame,provider:bundle.frames[i]?.provider||null,mode:bundle.frames[i]?.mode||'UNAVAILABLE',ageMs:Number(bundle.frames[i]?.ageMs||0)}));ideal.rationale=[...(ideal.rationale||[]),bundle.mode==='FRESH_CANDLES'?'Watch TF data fresh on all required frames':`Watch uses recent validated TF cache; max age ${Math.round(bundle.ageMs/60000)}m`];return ideal;}catch{return null;}
}'''
w=rep(w,old,new,'ideal analyzer')
w=rep(w,'const ideal=await analyzeWatchIdealReference(ticker,style);','const ideal=await analyzeWatchIdealReference(ticker,style,env);','watch ideal call')

# Seed the Watch TF cache opportunistically whenever the primary scanner already has valid candles.
old2="const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;\n    const setup=buildCryptoSetup(t,style,stats);"
new2="const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;\n    if(typeof putWatchTfCacheV3221==='function'){for(let i=0;i<intervalMap[style].length;i++)await putWatchTfCacheV3221(globalThis.__signalhubEnv||null,t.symbol,intervalMap[style][i],stats[i],String(t.exchange||t.venue||t.provider||''));}\n    const setup=buildCryptoSetup(t,style,stats);"
# Do not inject scanner cache here because analyzeCryptoCandidate does not receive env. Watch endpoint remains self-seeding safely.

# Add truthful Watch data-mode display in Android detail blocks.
old3='if(!story.isEmpty())c.addView(tv(story,9,MUTED,false));JSONArray rat=x.optJSONArray("rationale");'
new3='String dm=x.optString("watchDataMode","");if(!dm.isEmpty()){long age=x.optLong("watchDataAgeMs",0);c.addView(tv(dm.equals("FRESH_CANDLES")?"DATA • FRESH CANDLES":"DATA • RECENT VALID CACHE • "+Math.max(0,age/60000)+"m",8,dm.equals("FRESH_CANDLES")?GREEN:YELLOW,true));}if(!story.isEmpty())c.addView(tv(story,9,MUTED,false));JSONArray rat=x.optJSONArray("rationale");'
a=rep(a,old3,new3,'android watch data mode')

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.22.1 resilient Watch TF pipeline')
