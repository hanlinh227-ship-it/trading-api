from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text(); a=A.read_text(); g=G.read_text()

def rep(text,old,new,label,count=1):
    if old not in text: raise SystemExit('missing '+label)
    return text.replace(old,new,count)

# Release identity
w=rep(w,'SIGNALHUB-V3-GATEWAY-3.20.1','SIGNALHUB-V3-GATEWAY-3.21.0','worker version')
a=rep(a,'private static final String APP_VERSION="3.20.1";','private static final String APP_VERSION="3.21.0";','app version')
g=rep(g,'versionCode 27','versionCode 28','version code')
g=rep(g,"versionName '3.20.1'","versionName '3.21.0'",'version name')
w=w.replace("versionCode: 27,\n  versionName: '3.20.1',","versionCode: 28,\n  versionName: '3.21.0',",1)
w=w.replace("title: 'SignalHub 3.20.1 Stable100 Liquidity Normalized'","title: 'SignalHub 3.21 Standardized Data + Ideal Watchlist'",1)
w=w.replace("artifactName: 'SignalHub-Android-v3.20.1-Stable100-LiquidityFix'","artifactName: 'SignalHub-Android-v3.21.0-Standardized-Watch-Ideal'",1)

# Never inherit an older ticker last-good cache after a schema update.
w=w.replace("v31:crypto:tickers:lastgood","v321:crypto:tickers:lastgood:schema3")

# Stable100: strict versioned schema + normalized multi-venue composite.
start=w.index('const STABLE100_SIZE=100;')
end=w.index('function rotatingStableCandidates',start)
stable_block=r'''const STABLE100_SIZE=100;
const CRYPTO_DATA_SCHEMA='CRYPTO_MARKET_ROW_V3';
const CRYPTO_NORMALIZATION_VERSION='2026-09-STANDARDIZED-LIQUIDITY-V3';
const STABLE100_CACHE_KEY='v321:crypto:stable100:schema3';
const STABLE100_RANKING='QUALITY_TIER_THEN_QUOTE_TURNOVER_OI_SPREAD_MOVE';
const NON_CRYPTO_BASE_EXCLUDE=new Set([
  'AAPL','NVDA','TSLA','INTC','MU','MSTR','SOXL','SPCX','SKHYNIX','SKHY','SNDK','GOOGL','GOOG','META','AMZN','MSFT','AMD','NFLX','COIN','HOOD','PLTR','AVGO','TSM','ARM','ORCL','QCOM','SMCI','MARA','RIOT','QQQ','SPY','DIA','IWM','XAU','XAG','PAXG','XAUT','GOLD','SILVER','WTI','BRENT','USOIL','UKOIL'
]);
function cryptoOnlyUniverseRow(t){
  const symbol=canonical(t?.symbol||''),base=symbol.replace(/USDT$/,'');
  return !!symbol&&symbol.endsWith('USDT')&&!STABLE_BASE_EXCLUDE.has(base)&&!NON_CRYPTO_BASE_EXCLUDE.has(base)&&!/^(AAPL|NVDA|TSLA|MSFT|AMZN|META|GOOG|INTC|AMD|MSTR|XAU|XAG)/.test(base);
}
function normalizeStable100Row(t){
  if(!t||!(Number(t.lastPrice)>0)||!cryptoOnlyUniverseRow(t))return null;
  const symbol=canonical(t.symbol),venue=String(t.exchange||t.provider||'UNKNOWN').toUpperCase(),turn=Number(t.turnover24h||0),spread=t.spreadBps==null?999:Number(t.spreadBps),move=Number(t.change24hPct||0),oi=t.openInterestValue==null?null:Number(t.openInterestValue),fund=t.fundingRate==null?null:Number(t.fundingRate);
  if(!['BYBIT','OKX','BINANCE'].includes(venue)||!(turn>0)||!(spread>=0)||!Number.isFinite(move))return null;
  return {...t,symbol,canonicalSymbol:symbol,assetClass:'CRYPTO',schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,venue,exchange:venue,provider:venue,source:String(t.source||venue),turnover24hQuote:turn,turnover24h:turn,spreadBps:spread,change24hPct:move,openInterestValue:oi,fundingRate:fund,sourceReceivedAt:t.receivedAt||null};
}
function stable100QualityTier(t){
  const turn=Number(t?.turnover24hQuote||0),spread=Number(t?.spreadBps??999),move=Math.abs(Number(t?.change24hPct||0)),oi=t?.openInterestValue==null?null:Number(t.openInterestValue),fund=t?.fundingRate==null?null:Math.abs(Number(t.fundingRate));
  const oiOk=(floor)=>oi==null||!Number.isFinite(oi)||oi<=0||oi>=floor, fundOk=(cap)=>fund==null||!Number.isFinite(fund)||fund<=cap;
  if(turn>=20_000_000&&spread<=15&&move<=35&&oiOk(1_000_000)&&fundOk(.008))return 'A';
  if(turn>=5_000_000&&spread<=20&&move<=45&&oiOk(500_000)&&fundOk(.012))return 'B';
  if(turn>=250_000&&spread<=50&&move<=80&&oiOk(50_000)&&fundOk(.050))return 'C';
  return null;
}
function stable100Compare(a,b){
  const q={A:0,B:1,C:2},qa=q[a.qualityTier]??9,qb=q[b.qualityTier]??9;if(qa!==qb)return qa-qb;
  const at=Number(a.turnover24hQuote||0),bt=Number(b.turnover24hQuote||0);if(at!==bt)return bt-at;
  const ao=Number(a.openInterestValue||0),bo=Number(b.openInterestValue||0);if(ao!==bo)return bo-ao;
  const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;
  const am=Math.abs(Number(a.change24hPct||0)),bm=Math.abs(Number(b.change24hPct||0));if(am!==bm)return am-bm;
  return String(a.symbol||'').localeCompare(String(b.symbol||''));
}
function bestVenueRow(rows){return [...rows].sort((a,b)=>{const at=Number(a.turnover24hQuote||0),bt=Number(b.turnover24hQuote||0);if(at!==bt)return bt-at;const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;return Number(b.openInterestValue||0)-Number(a.openInterestValue||0);})[0];}
function buildStable100Universe(rows){
  const grouped=new Map();
  for(const raw of rows||[]){const n=normalizeStable100Row(raw);if(!n)continue;const tier=stable100QualityTier(n);if(!tier)continue;n.qualityTier=tier;const arr=grouped.get(n.symbol)||[];arr.push(n);grouped.set(n.symbol,arr);}
  const picked=[];for(const arr of grouped.values()){const best=bestVenueRow(arr),venues=[...new Set(arr.map(x=>x.venue))];picked.push({...best,venueCandidates:venues,venueCount:venues.length});}
  return picked.sort(stable100Compare).slice(0,STABLE100_SIZE).map((x,i)=>({...x,rank:i+1}));
}
async function loadStable100CompositeSnapshot(env){
  const providers=['BYBIT','OKX','BINANCE'],snaps=await Promise.all(providers.map(p=>cryptoSnapshotForProvider(env,p))),live=snaps.filter(s=>s?.live!==false&&Array.isArray(s.rows)&&s.rows.length>0),rows=[];
  for(const s of live)for(const r of s.rows)rows.push({...r,exchange:String(r.exchange||s.provider).toUpperCase(),provider:String(s.provider).toUpperCase(),receivedAt:s.receivedAt});
  if(!rows.length)throw new Error('ALL_STABLE100_PROVIDERS_UNAVAILABLE');
  const receivedAt=live.map(s=>s.receivedAt).filter(Boolean).sort().pop()||nowIso();
  return {provider:'MULTI_VENUE_COMPOSITE',providers:live.map(s=>String(s.provider).toUpperCase()),receivedAt,rows};
}
function stable100PayloadValid(p){
  if(!p||p.version!==V3_VERSION||p.schemaVersion!==CRYPTO_DATA_SCHEMA||p.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION||p.target!==STABLE100_SIZE||p.count!==STABLE100_SIZE||p.complete!==true)return false;
  if(!Array.isArray(p.rows)||!Array.isArray(p.symbols)||p.rows.length!==STABLE100_SIZE||p.symbols.length!==STABLE100_SIZE||new Set(p.symbols).size!==STABLE100_SIZE)return false;
  if(p.rows.some((r,i)=>r.assetClass!=='CRYPTO'||r.schemaVersion!==CRYPTO_DATA_SCHEMA||r.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION||canonical(r.symbol)!==r.canonicalSymbol||!cryptoOnlyUniverseRow(r)||r.rank!==i+1||!['A','B','C'].includes(r.qualityTier)))return false;
  const age=Date.now()-Date.parse(p.refreshedAt||0);return Number.isFinite(age)&&age>=0&&age<=180000;
}
async function readStable100(env){
  if(!env?.SIGNALS_KV)return null;const raw=await env.SIGNALS_KV.get(STABLE100_CACHE_KEY);if(!raw)return null;try{const p=JSON.parse(raw);return stable100PayloadValid(p)?p:null;}catch{return null;}
}
async function persistStable100(env,snap,rows){
  const cached=await readStable100(env),cacheAge=cached?Date.now()-Date.parse(cached.refreshedAt||0):Infinity;if(cached&&cacheAge<45000)return cached.rows;
  let composite=null;try{composite=await loadStable100CompositeSnapshot(env);}catch{}
  const sourceRows=composite?.rows?.length?composite.rows:(rows||[]),universe=buildStable100Universe(sourceRows),providers=composite?.providers||[snap?.provider].filter(Boolean),at=nowIso();
  if(universe.length<STABLE100_SIZE){if(cached&&cacheAge<=180000)return cached.rows;return universe;}
  const payload={version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,assetClass:'CRYPTO',provider:composite?.provider||snap?.provider||null,providers,receivedAt:composite?.receivedAt||snap?.receivedAt||at,refreshedAt:at,target:STABLE100_SIZE,count:STABLE100_SIZE,complete:true,ranking:STABLE100_RANKING,turnoverNormalization:'BYBIT_QUOTE_TURNOVER|OKX_BASE_VOL_X_LAST|BINANCE_QUOTE_VOLUME',symbols:universe.map(x=>x.symbol),rows:universe};
  if(env?.SIGNALS_KV)await env.SIGNALS_KV.put(STABLE100_CACHE_KEY,JSON.stringify(payload),{expirationTtl:240});
  return universe;
}
function stable100Integrity(p){
  const problems=[];if(!p)problems.push('NO_VALID_STANDARDIZED_STABLE100');else{if(p.version!==V3_VERSION)problems.push('VERSION_MISMATCH');if(p.schemaVersion!==CRYPTO_DATA_SCHEMA)problems.push('SCHEMA_MISMATCH');if(p.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION)problems.push('NORMALIZATION_MISMATCH');if(p.count!==STABLE100_SIZE)problems.push('COUNT_NOT_100');if((p.rows||[]).some(r=>!cryptoOnlyUniverseRow(r)))problems.push('NON_CRYPTO_ROW');}
  return {ok:problems.length===0,problems};
}
'''
w=w[:start]+stable_block+w[end:]

# Policy metadata makes update compatibility explicit.
w=w.replace("stableUniversePolicy:'TOP_100_STABLE_USDT_PERP_DYNAMIC'","stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC'",1)
w=w.replace("continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES'","continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES',dataSchema:'CRYPTO_MARKET_ROW_V3',normalizationVersion:'2026-09-STANDARDIZED-LIQUIDITY-V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT'",1)

# Ideal Watch reference engine. It shares live candles/tfStats but never becomes an active signal.
needle='async function analyzeCryptoCandidate(t,style){'
if needle not in w: raise SystemExit('analyzeCryptoCandidate missing')
watch_helper=r'''function buildWatchIdealReference(t,style,stats){
  const [a,b,c]=stats,px=Number(t?.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,atr=Number(a.atr),spread=Math.max(0,Number(t.spreadBps||0)),spreadPx=px*spread/10000;
  const vote=2*Number(b.trend||0)+2*Number(c.trend||0)+Number(a.trend||0)+Number(a.momentum||0)+Number(b.momentum||0);
  let dir=vote>0?1:vote<0?-1:0;if(!dir){const ref=Number(b.ema50||a.ema50||px);dir=px>=ref?1:-1;}
  const entryBuffer=Math.max(atr*(style==='SCALP'?.06:.11),spreadPx*3),pbRaw=dir>0?Math.max(Number(a.ema20||px),Number(a.recentLow||a.low)+.28*atr):Math.min(Number(a.ema20||px),Number(a.recentHigh||a.high)-.28*atr);
  const pb=dir>0?Math.min(px-entryBuffer,pbRaw):Math.max(px+entryBuffer,pbRaw),pbDistance=Math.abs(px-pb),preferLimit=pbDistance<=atr*(style==='SCALP'?1.45:2.10)&&Math.abs(vote)>=1;
  const orderType=preferLimit?'LIMIT':'STOP',entry=preferLimit?pb:(dir>0?Math.max(px+entryBuffer,Number(a.recentHigh||a.high)+entryBuffer):Math.min(px-entryBuffer,Number(a.recentLow||a.low)-entryBuffer)),entryModel=preferLimit?'WATCH_IDEAL_STRUCTURE_PULLBACK_LIMIT':'WATCH_IDEAL_CONFIRMATION_STOP';
  const stopBuffer=Math.max(atr*(style==='SCALP'?.24:.38),spreadPx*(style==='SCALP'?3.4:4.0)),anchor=dir>0?Math.min(Number(a.recentLow||a.low),Number(a.low),Number(a.ema50||a.low)-.06*atr):Math.max(Number(a.recentHigh||a.high),Number(a.high),Number(a.ema50||a.high)+.06*atr);
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr*(style==='SCALP'?.78:1.10);if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0))return null;
  const hi=(vals,f)=>Math.max(...vals.filter(Number.isFinite),f),lo=(vals,f)=>Math.min(...vals.filter(Number.isFinite),f);let tp1,tp2,tp3;
  if(dir>0){tp1=hi([a.priorHigh,a.recentHigh],entry+risk*.95);tp2=hi([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=hi([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.20:2.85)));}
  else{tp1=lo([a.priorLow,a.recentLow],entry-risk*.95);tp2=lo([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=lo([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.20:2.85)));}
  const distance=Math.abs(entry-px),distancePct=distance/px*100,rr=Math.abs(tp3-entry)/risk,regime=style==='SCALP'?'WATCH_IDEAL_MICROSTRUCTURE':'WATCH_IDEAL_HTF_STRUCTURE',story=style==='SCALP'?'Kế hoạch SCALP lý tưởng để tham khảo: chờ pullback hoặc xác nhận 5m trong bối cảnh 15m/1h.':'Kế hoạch SWING lý tưởng để tham khảo: chờ H1 khớp với cấu trúc H4/D1.';
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:'REFERENCE',lifecycle:'REFERENCE_ONLY',entryState:'REFERENCE_ONLY',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cryptoRiskCluster(t.symbol),marketRegime:regime,marketStory:story,judgment:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STUDY ONLY`,entryModel,slModel:'WATCH_STRUCTURE_INVALIDATION_PLUS_ATR_SPREAD_BUFFER',tpModel:'WATCH_STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:'REFERENCE_ONLY',watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false,referenceReason:'BEST_CONDITIONAL_STRUCTURE_PLAN_NOT_ACTIVE_SIGNAL',distanceToEntryAbs:Number(distance.toPrecision(8)),distanceToEntryPct:Number(distancePct.toFixed(4)),technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,'SL ngoài vùng vô hiệu cấu trúc + buffer ATR/spread','Watchlist reference only — không chiếm slot, không tính performance']},'CRYPTO',style);
}
async function analyzeWatchIdealReference(t,style){
  try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildWatchIdealReference(t,style,stats);}catch{return null;}
}
async function findWatchTickerMulti(symbol,primarySnap,env){
  let t=(primarySnap?.rows||[]).find(x=>canonical(x.symbol)===symbol);if(t&&primarySnap?.live!==false)return {ticker:t,snap:primarySnap};
  const primary=String(primarySnap?.provider||'').toUpperCase();for(const p of ['BYBIT','OKX','BINANCE']){if(p===primary)continue;const s=await cryptoSnapshotForProvider(env,p);t=(s.rows||[]).find(x=>canonical(x.symbol)===symbol);if(t&&s.live!==false)return {ticker:t,snap:s};}
  return {ticker:null,snap:primarySnap};
}

'''
w=w.replace(needle,watch_helper+needle,1)

# Watch projection exposes reference-isolation fields.
wf_start=w.index('function watchFlatSignal(src,state,assessment){')
wf_end=w.index('async function loadWatchSnapshot',wf_start)
watch_flat=r'''function watchFlatSignal(src,state,assessment){
  const s=src||{},a=assessment||s.entryAssessment||{};
  return {state,activeSignal:state==='ACTIVE_SIGNAL',symbol:s.symbol||null,side:s.side||null,orderType:s.orderType||null,status:s.status||null,entry:num(s.actualEntry??s.entry),sl:num(s.sl),tp1:num(s.tp1),tp2:num(s.tp2),tp3:num(s.tp3??s.tp),targetRR:num(s.targetRR),marketRegime:s.marketRegime||null,marketStory:s.marketStory||null,judgment:s.judgment||null,entryModel:s.entryModel||null,coverageTier:s.coverageTier||null,coverageFallback:Boolean(s.coverageFallback),assessmentMethod:a.method||null,failedChecks:Array.isArray(a.failed)?a.failed:[],rationale:Array.isArray(s.rationale)?s.rationale.slice(0,6):[],provider:s.executionPriceAuthority||s.provider||s.exchange||null,issuedAt:s.issuedAt||null,lastCheckedAt:s.lastCheckedAt||null,watchReference:Boolean(s.watchReference),studyOnly:Boolean(s.studyOnly),occupiesActiveSlot:s.occupiesActiveSlot===false?false:state==='ACTIVE_SIGNAL',performanceEligible:s.performanceEligible===false?false:state==='ACTIVE_SIGNAL',distanceToEntryAbs:num(s.distanceToEntryAbs),distanceToEntryPct:num(s.distanceToEntryPct)};
}
'''
w=w[:wf_start]+watch_flat+w[wf_end:]

# Replace Watch analysis as one coherent read-only implementation.
wa_start=w.index('async function watchAnalyze(url,env){')
wa_end=w.index('async function unifiedSignals',wa_start)
watch_analyze=r'''async function watchAnalyze(url,env){
  const symbol=normalizeWatchSymbol(url.searchParams.get('symbol')||'');if(!symbol)return json({ok:false,version:V3_VERSION,error:'BAD_WATCH_SYMBOL'},400);
  const primary=await loadWatchSnapshot(env),resolved=await findWatchTickerMulti(symbol,primary,env),snap=resolved.snap||primary,ticker=resolved.ticker,fresh=snap?.live!==false;
  if(!ticker){const unavailable=watchUnavailable(symbol,snap?.provider,'SYMBOL_NOT_AVAILABLE_ON_LIVE_CRYPTO_VENUES');return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:null,dataHealth:{state:'UNAVAILABLE',live:false,staleFallback:false,provider:snap?.provider||null,providerErrors:snap?.errors||[]},styles:{SCALP:unavailable,SWING:{...unavailable}},activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist is read-only and never consumes active slots.'},analyzedAt:nowIso()});}
  const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null};
  if(!fresh){const unavailable=watchUnavailable(symbol,baseTicker.provider,'FRESH_TICKER_UNAVAILABLE');return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:baseTicker,dataHealth:{state:'STALE',live:false,staleFallback:true,receivedAt:snap.receivedAt||null,provider:baseTicker.provider},styles:{SCALP:unavailable,SWING:{...unavailable}},activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist is read-only and never consumes active slots.'},analyzedAt:nowIso()});}
  const activeBook=await getActiveBook(env),styles={};
  await Promise.all(['SCALP','SWING'].map(async style=>{
    const active=activeBook.find(x=>String(x.style||'').toUpperCase()===style&&canonical(x.symbol)===symbol);if(active){styles[style]=watchFlatSignal(active,'ACTIVE_SIGNAL',active.entryAssessment);return;}
    const setup=await analyzeCryptoCandidate(ticker,style);
    if(setup){const strict=assessEntrySetup(setup),conditional=setup.coverageFallback?assessCoverageSetup(setup):strict,state=strict.verdict==='PASS'?'TRADEABLE_NOW':conditional.verdict==='PASS'?'CONDITIONAL_WAIT':'NO_TRADE';if(state!=='NO_TRADE'){const projected={...setup,watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false};styles[style]=watchFlatSignal(projected,state,state==='TRADEABLE_NOW'?strict:conditional);return;}}
    const ideal=await analyzeWatchIdealReference(ticker,style);if(ideal){styles[style]=watchFlatSignal(ideal,'IDEAL_REFERENCE',null);return;}
    styles[style]=watchUnavailable(symbol,baseTicker.provider,'ANALYSIS_CANDLES_UNAVAILABLE');
  }));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:baseTicker,dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:snap.receivedAt||null,provider:baseTicker.provider,providerErrors:snap.errors||[]},styles,activeBook:{targetScalp:10,targetSwing:5,note:'Watchlist ideal plans are study-only; they never consume or replace the 15 active slots and never enter performance history.'},analyzedAt:nowIso()});
}

'''
w=w[:wa_start]+watch_analyze+w[wa_end:]

# Stable100 + integrity routes, replaced by route boundaries.
r_start=w.index("if(url.pathname==='/v3/crypto/stable100'&&req.method==='GET')")
r_end=w.index("if(url.pathname==='/v3/crypto/monitor'",r_start)
routes=r'''if(url.pathname==='/v3/crypto/stable100'&&req.method==='GET'){let cached=await readStable100(env);if(!cached){const snap=await loadCryptoSnapshot(env);await persistStable100(env,snap,snap.rows);cached=await readStable100(env);}if(cached)return json({ok:true,...cached,integrity:stable100Integrity(cached)});return json({ok:false,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,error:'NO_VALID_STANDARDIZED_STABLE100'},503);}
    if(url.pathname==='/v3/data-integrity'&&req.method==='GET'){const p=await readStable100(env),audit=stable100Integrity(p);return json({ok:audit.ok,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,stable100:p?{count:p.count,target:p.target,provider:p.provider,providers:p.providers,refreshedAt:p.refreshedAt,complete:p.complete}:null,problems:audit.problems});}
    '''
w=w[:r_start]+routes+w[r_end:]

# Android Watch UI: ideal-reference state and full Entry/SL/TP ladder.
a=a.replace('WATCHLIST • TÌM & PHÂN TÍCH COIN','WATCHLIST • LỆNH LÝ TƯỞNG • THAM KHẢO')
a=a.replace('Tìm coin theo mã • không chiếm 15 slot tín hiệu chính','Luôn hiển thị Entry/SL/TP tham khảo khi dữ liệu hợp lệ • không chiếm 15 slot')
sc=a.index('private int watchStateColor(String state)')
se=a.index('private View watchStyleBlock',sc)
state_methods='''private int watchStateColor(String state){String x=state==null?"":state.toUpperCase(Locale.US);if(x.equals("ACTIVE_SIGNAL"))return GREEN;if(x.equals("TRADEABLE_NOW"))return CYAN;if(x.equals("CONDITIONAL_WAIT")||x.equals("IDEAL_REFERENCE")||x.equals("DATA_UNAVAILABLE"))return YELLOW;return RED;}\n    private String watchStateVi(String state){String x=state==null?"":state.toUpperCase(Locale.US);return switch(x){case "ACTIVE_SIGNAL"->"CÓ LỆNH";case "TRADEABLE_NOW"->"SETUP ĐẸP";case "CONDITIONAL_WAIT"->"CHỜ ĐIỀU KIỆN";case "IDEAL_REFERENCE"->"LỆNH LÝ TƯỞNG";case "DATA_UNAVAILABLE"->"DỮ LIỆU TẠM THIẾU";case "NO_TRADE"->"NO TRADE";default->"ĐANG PHÂN TÍCH";};}\n    '''
a=a[:sc]+state_methods+a[se:]
ui_start=a.index('private View watchStyleBlock(String styleName,JSONObject x)')
ui_end=a.index('private void renderWatchlist',ui_start)
ui_method='''private View watchStyleBlock(String styleName,JSONObject x){LinearLayout c=column();c.setPadding(0,dp(9),0,dp(4));String state=x==null?"LOADING":x.optString("state","DATA_UNAVAILABLE"),side=sideVi(x==null?"":x.optString("side","")),order=x==null?"":x.optString("orderType","");LinearLayout h=row();h.addView(tv(styleName,11,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(watchStateVi(state),watchStateColor(state)));c.addView(h);if(x==null){TextView z=tv("Đang đọc cấu trúc…",9,MUTED,false);z.setPadding(0,dp(5),0,0);c.addView(z);return c;}String regime=x.optString("marketRegime","");if(!side.isEmpty()&&!order.isEmpty()){TextView d=tv(side+" • "+order+(regime.isEmpty()?"":" • "+regime),10,side.equals("BUY")?GREEN:RED,true);d.setPadding(0,dp(5),0,0);c.addView(d);}else if(!regime.isEmpty()){TextView d=tv(regime,9,MUTED,true);d.setPadding(0,dp(5),0,0);c.addView(d);}double e=x.optDouble("entry",0),sl=x.optDouble("sl",0),tp1=x.optDouble("tp1",0),tp2=x.optDouble("tp2",0),tp3=x.optDouble("tp3",0);if(e>0&&sl>0&&tp3>0){c.addView(tv("Entry "+fmt(e)+"  •  SL "+fmt(sl),9,TEXT,true));c.addView(tv("TP1 "+fmt(tp1)+"  •  TP2 "+fmt(tp2)+"  •  TP3 "+fmt(tp3),9,GREEN,true));}if(state.equals("IDEAL_REFERENCE")){double d=x.optDouble("distanceToEntryPct",-1);c.addView(tv("THAM KHẢO • KHÔNG PHẢI LỆNH ACTIVE"+(d>=0?"  •  CÁCH ENTRY "+String.format(Locale.US,"%.2f%%",d):""),8,YELLOW,true));}String story=x.optString("marketStory","");if(!story.isEmpty()&&(state.equals("TRADEABLE_NOW")||state.equals("ACTIVE_SIGNAL")||state.equals("CONDITIONAL_WAIT")||state.equals("IDEAL_REFERENCE")))c.addView(tv(story,9,MUTED,false));JSONArray failed=x.optJSONArray("failedChecks");if(state.equals("DATA_UNAVAILABLE")&&failed!=null&&failed.length()>0)c.addView(tv("Dữ liệu: "+failed.optString(0),8,YELLOW,false));return c;}\n    '''
a=a[:ui_start]+ui_method+a[ui_end:]

# Explicit data-integrity wording in Sources screen.
a=a.replace('Bybit ưu tiên; OKX/Binance fallback được gắn đúng nguồn. Entry/SL/TP lifecycle luôn dùng đúng executionPriceAuthority của từng tín hiệu.','Stable100 chuẩn hóa đa nguồn Bybit + OKX + Binance; cache cũ/sai version-schema bị loại. Mỗi tín hiệu vẫn giữ đúng executionPriceAuthority.',1)
a=a.replace('SCALP và SWING tách riêng. Không giả win-rate dự đoán; chỉ thống kê TP/SL đã đóng. Quote lỗi không được giả thành LIVE.','SCALP và SWING tách riêng. CRYPTO_MARKET_ROW_V3 khóa chuẩn dữ liệu qua các bản cập nhật. Không giả win-rate; quote lỗi không được giả thành LIVE.',1)

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.21 FINAL standardized data + ideal Watchlist')
