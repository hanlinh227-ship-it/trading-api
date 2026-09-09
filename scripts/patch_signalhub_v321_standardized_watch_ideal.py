from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text();a=A.read_text();g=G.read_text()

def rep(text,old,new,label):
    if old not in text: raise SystemExit('missing '+label)
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# V3.21 release identity. Schema/cache identity now moves with engine version.
# -----------------------------------------------------------------------------
w=rep(w,'SIGNALHUB-V3-GATEWAY-3.20.1','SIGNALHUB-V3-GATEWAY-3.21.0','worker version')
a=rep(a,'private static final String APP_VERSION="3.20.1";','private static final String APP_VERSION="3.21.0";','app version')
g=rep(g,'versionCode 27','versionCode 28','version code')
g=rep(g,"versionName '3.20.1'","versionName '3.21.0'",'version name')
w=w.replace("versionCode: 27,\n  versionName: '3.20.1',","versionCode: 28,\n  versionName: '3.21.0',",1)
w=w.replace("title: 'SignalHub 3.20.1 Stable100 Liquidity Normalized'","title: 'SignalHub 3.21 Standardized Data + Ideal Watchlist'",1)
w=w.replace("artifactName: 'SignalHub-Android-v3.20.1-Stable100-LiquidityFix'","artifactName: 'SignalHub-Android-v3.21.0-Standardized-Watch-Ideal'",1)

# -----------------------------------------------------------------------------
# Replace V3.20 Stable100 storage/ranking with version-safe normalized composite.
# - New cache namespace prevents a new engine from serving an older snapshot.
# - Rows carry schema/normalization metadata.
# - BYBIT/OKX/BINANCE are merged by canonical symbol.
# - Tokenized TradFi/metals are excluded from the crypto universe.
# - Quality tiers fill 100 without pretending all tiers are equally liquid.
# -----------------------------------------------------------------------------
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
  const symbol=canonical(t.symbol),venue=String(t.exchange||t.provider||t.source||'UNKNOWN').toUpperCase(),turn=Number(t.turnover24h||0),spread=t.spreadBps==null?999:Number(t.spreadBps),move=Number(t.change24hPct||0),oi=t.openInterestValue==null?null:Number(t.openInterestValue),fund=t.fundingRate==null?null:Number(t.fundingRate);
  if(!(turn>0)||!(spread>=0)||!Number.isFinite(move))return null;
  return {...t,symbol,canonicalSymbol:symbol,assetClass:'CRYPTO',schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,venue,exchange:venue,provider:venue,source:venue,turnover24hQuote:turn,turnover24h:turn,spreadBps:spread,change24hPct:move,openInterestValue:oi,fundingRate:fund,sourceReceivedAt:t.receivedAt||null};
}
function stable100QualityTier(t){
  const turn=Number(t?.turnover24hQuote||t?.turnover24h||0),spread=Number(t?.spreadBps??999),move=Math.abs(Number(t?.change24hPct||0)),oi=t?.openInterestValue==null?null:Number(t.openInterestValue),fund=t?.fundingRate==null?null:Math.abs(Number(t.fundingRate));
  const oiOk=(floor)=>oi==null||!Number.isFinite(oi)||oi<=0||oi>=floor, fundOk=(cap)=>fund==null||!Number.isFinite(fund)||fund<=cap;
  if(turn>=20_000_000&&spread<=15&&move<=35&&oiOk(1_000_000)&&fundOk(.008))return 'A';
  if(turn>=5_000_000&&spread<=20&&move<=45&&oiOk(500_000)&&fundOk(.012))return 'B';
  if(turn>=1_000_000&&spread<=30&&move<=60&&oiOk(150_000)&&fundOk(.020))return 'C';
  return null;
}
function stable100Compare(a,b){
  const q={A:0,B:1,C:2},qa=q[a.qualityTier]??9,qb=q[b.qualityTier]??9;if(qa!==qb)return qa-qb;
  const at=Number(a.turnover24hQuote||a.turnover24h||0),bt=Number(b.turnover24hQuote||b.turnover24h||0);if(at!==bt)return bt-at;
  const ao=Number(a.openInterestValue||0),bo=Number(b.openInterestValue||0);if(ao!==bo)return bo-ao;
  const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;
  const am=Math.abs(Number(a.change24hPct||0)),bm=Math.abs(Number(b.change24hPct||0));if(am!==bm)return am-bm;
  return String(a.symbol||'').localeCompare(String(b.symbol||''));
}
function bestVenueRow(rows){return [...rows].sort((a,b)=>{const at=Number(a.turnover24hQuote||0),bt=Number(b.turnover24hQuote||0);if(at!==bt)return bt-at;const as=Number(a.spreadBps??999),bs=Number(b.spreadBps??999);if(as!==bs)return as-bs;return Number(b.openInterestValue||0)-Number(a.openInterestValue||0);})[0];}
function buildStable100Universe(rows){
  const grouped=new Map();
  for(const raw of rows||[]){const n=normalizeStable100Row(raw);if(!n)continue;const tier=stable100QualityTier(n);if(!tier)continue;n.qualityTier=tier;const arr=grouped.get(n.symbol)||[];arr.push(n);grouped.set(n.symbol,arr);}
  const picked=[];for(const [symbol,arr] of grouped){const best=bestVenueRow(arr),venues=[...new Set(arr.map(x=>x.venue))];picked.push({...best,venueCandidates:venues,venueCount:venues.length});}
  return picked.sort(stable100Compare).slice(0,STABLE100_SIZE).map((x,i)=>({...x,rank:i+1}));
}
async function loadStable100CompositeSnapshot(){
  const providers=['BYBIT','OKX','BINANCE'],snaps=await Promise.all(providers.map(p=>loadCryptoSnapshotFor(p))),live=snaps.filter(s=>Array.isArray(s.rows)&&s.rows.length>0),rows=[];
  for(const s of live)for(const r of s.rows)rows.push({...r,exchange:String(r.exchange||s.provider).toUpperCase(),provider:String(s.provider).toUpperCase(),source:String(r.source||s.provider).toUpperCase(),receivedAt:s.receivedAt});
  if(!rows.length)throw new Error('ALL_STABLE100_PROVIDERS_UNAVAILABLE');
  const receivedAt=live.map(s=>s.receivedAt).filter(Boolean).sort().pop()||nowIso();
  return {provider:'MULTI_VENUE_COMPOSITE',providers:live.map(s=>s.provider),receivedAt,rows};
}
function stable100PayloadValid(p){
  if(!p||p.version!==V3_VERSION||p.schemaVersion!==CRYPTO_DATA_SCHEMA||p.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION||p.target!==STABLE100_SIZE)return false;
  if(!Array.isArray(p.rows)||!Array.isArray(p.symbols)||p.rows.length!==p.count||p.symbols.length!==p.count||new Set(p.symbols).size!==p.symbols.length)return false;
  if(p.rows.some(r=>r.assetClass!=='CRYPTO'||r.schemaVersion!==CRYPTO_DATA_SCHEMA||r.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION||canonical(r.symbol)!==r.canonicalSymbol||!cryptoOnlyUniverseRow(r)))return false;
  const age=Date.now()-Date.parse(p.refreshedAt||0);return Number.isFinite(age)&&age>=0&&age<=180000;
}
async function readStable100(env){
  if(!env?.SIGNALS_KV)return null;const raw=await env.SIGNALS_KV.get(STABLE100_CACHE_KEY);if(!raw)return null;try{const p=JSON.parse(raw);return stable100PayloadValid(p)?p:null;}catch{return null;}
}
async function persistStable100(env,snap,rows){
  const cached=await readStable100(env),cacheAge=cached?Date.now()-Date.parse(cached.refreshedAt||0):Infinity;if(cached&&cacheAge<45000)return cached.rows;
  let composite=null;try{composite=await loadStable100CompositeSnapshot();}catch{}
  const sourceRows=composite?.rows?.length?composite.rows:(rows||[]),universe=buildStable100Universe(sourceRows),providers=composite?.providers||[snap?.provider].filter(Boolean),at=nowIso();
  const payload={version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,assetClass:'CRYPTO',provider:composite?.provider||snap?.provider||null,providers,receivedAt:composite?.receivedAt||snap?.receivedAt||at,refreshedAt:at,target:STABLE100_SIZE,count:universe.length,complete:universe.length===STABLE100_SIZE,ranking:STABLE100_RANKING,turnoverNormalization:'BYBIT_QUOTE_TURNOVER|OKX_BASE_VOL_X_LAST|BINANCE_QUOTE_VOLUME',symbols:universe.map(x=>x.symbol),rows:universe};
  if(universe.length<STABLE100_SIZE&&cached&&cached.count===STABLE100_SIZE&&cacheAge<=180000){return cached.rows;}
  if(env?.SIGNALS_KV)await env.SIGNALS_KV.put(STABLE100_CACHE_KEY,JSON.stringify(payload),{expirationTtl:240});
  return universe;
}
function stable100Integrity(p){
  const problems=[];if(!p)problems.push('NO_VALID_CACHE');else{if(p.version!==V3_VERSION)problems.push('VERSION_MISMATCH');if(p.schemaVersion!==CRYPTO_DATA_SCHEMA)problems.push('SCHEMA_MISMATCH');if(p.normalizationVersion!==CRYPTO_NORMALIZATION_VERSION)problems.push('NORMALIZATION_MISMATCH');if(p.count!==100)problems.push('COUNT_NOT_100');if((p.rows||[]).some(r=>!cryptoOnlyUniverseRow(r)))problems.push('NON_CRYPTO_ROW');}
  return {ok:problems.length===0,problems};
}
'''
w=w[:start]+stable_block+w[end:]

# -----------------------------------------------------------------------------
# Watchlist ideal reference builder. It is explicitly study-only and never goes
# through writeV31Signal/reservation/performance. It uses the exact same candles,
# structure, ATR and spread context as the live engine, but is allowed to express
# the best conditional LIMIT/STOP even when active-trade confirmation is absent.
# -----------------------------------------------------------------------------
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
  const stopBuffer=Math.max(atr*(style==='SCALP'?.24:.38),spreadPx*(style==='SCALP'?3.4:4.0)),rawAnchor=dir>0?Math.min(Number(a.recentLow||a.low),Number(a.low),Number(a.ema50||a.low)-.06*atr):Math.max(Number(a.recentHigh||a.high),Number(a.high),Number(a.ema50||a.high)+.06*atr);
  let sl=dir>0?rawAnchor-stopBuffer:rawAnchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr*(style==='SCALP'?.78:1.10);if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0))return null;
  const hi=(vals,f)=>Math.max(...vals.filter(Number.isFinite),f),lo=(vals,f)=>Math.min(...vals.filter(Number.isFinite),f);let tp1,tp2,tp3;
  if(dir>0){tp1=hi([a.priorHigh,a.recentHigh],entry+risk*.95);tp2=hi([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=hi([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.20:2.85)));}
  else{tp1=lo([a.priorLow,a.recentLow],entry-risk*.95);tp2=lo([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=lo([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.20:2.85)));}
  const distance=Math.abs(entry-px),distancePct=px>0?distance/px*100:0,rr=Math.abs(tp3-entry)/risk,regime=style==='SCALP'?'WATCH_IDEAL_MICROSTRUCTURE':'WATCH_IDEAL_HTF_STRUCTURE',story=style==='SCALP'?'Kế hoạch SCALP lý tưởng để tham khảo: chờ pullback hoặc xác nhận 5m trong bối cảnh 15m/1h.':'Kế hoạch SWING lý tưởng để tham khảo: chờ H1 khớp với cấu trúc H4/D1.';
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:'REFERENCE',lifecycle:'REFERENCE_ONLY',entryState:'REFERENCE_ONLY',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cryptoRiskCluster(t.symbol),marketRegime:regime,marketStory:story,judgment:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STUDY ONLY`,entryModel,slModel:'WATCH_STRUCTURE_INVALIDATION_PLUS_ATR_SPREAD_BUFFER',tpModel:'WATCH_STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:Number(rawAnchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:'REFERENCE_ONLY',watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false,referenceReason:'BEST_CONDITIONAL_STRUCTURE_PLAN_NOT_ACTIVE_SIGNAL',distanceToEntryAbs:Number(distance.toPrecision(8)),distanceToEntryPct:Number(distancePct.toFixed(4)),qualityEvidence:{contextAligned:Math.abs(vote)>=1,liquidityEvent:false,displacementConfirmed:false,structureReclaimed:false,secondaryProviderConfirmed:false,entryNotChasing:true,invalidationStructural:true,targetPathClear:true,studyOnly:true},technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,turnover24h:Number(t.turnover24h||0),change24hPct:Number(t.change24hPct||0),openInterestValue:t.openInterestValue==null?null:Number(t.openInterestValue),fundingRate:t.fundingRate==null?null:Number(t.fundingRate),recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,'SL ngoài vùng vô hiệu cấu trúc + buffer ATR/spread','Watchlist reference only — không chiếm slot, không tính performance']},'CRYPTO',style);
}
async function analyzeWatchIdealReference(t,style){
  try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildWatchIdealReference(t,style,stats);}catch{return null;}
}
async function findWatchTicker(symbol,primarySnap){
  const found=primarySnap?.rows?.find(x=>canonical(x.symbol)===symbol);if(found)return found;
  for(const p of ['BYBIT','OKX','BINANCE']){if(String(primarySnap?.provider||'').toUpperCase()===p)continue;const s=await loadCryptoSnapshotFor(p);const t=s.rows?.find(x=>canonical(x.symbol)===symbol);if(t)return t;}
  return null;
}

'''
w=w.replace(needle,watch_helper+needle,1)

# Watch endpoint: use alternate live venue when primary does not list the symbol.
old="const snap=await loadCryptoSnapshot(env),ticker=snap.rows.find(x=>canonical(x.symbol)===symbol);\n  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_ON_LIVE_PROVIDER',provider:snap.provider},404);"
new="const snap=await loadCryptoSnapshot(env),ticker=await findWatchTicker(symbol,snap);\n  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_ON_LIVE_CRYPTO_VENUES',provider:snap.provider},404);"
w=rep(w,old,new,'watch multi venue ticker')

old_no="""if(!setup){
        styles[style]={state:'NO_TRADE',style,symbol,side:null,orderType:null,marketRegime:'NO_VALID_STRUCTURE',marketStory:'Cấu trúc hiện tại chưa đủ rõ để mở lệnh; tiếp tục theo dõi.',entry:null,sl:null,tp1:null,tp2:null,tp3:null,failedChecks:['NO_STRUCTURAL_SETUP'],checks:null};
        continue;
      }"""
new_no="""if(!setup){
        const ideal=await analyzeWatchIdealReference(ticker,style);
        if(ideal){styles[style]={state:'IDEAL_REFERENCE',...signalWatchProjection(ideal),entry:ideal.entry,sl:ideal.sl,tp1:ideal.tp1,tp2:ideal.tp2,tp3:ideal.tp3,watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false,distanceToEntryAbs:ideal.distanceToEntryAbs,distanceToEntryPct:ideal.distanceToEntryPct,failedChecks:['ACTIVE_CONFIRMATION_NOT_READY'],checks:null};continue;}
        styles[style]={state:'DATA_UNAVAILABLE',style,symbol,side:null,orderType:null,marketRegime:'REFERENCE_DATA_UNAVAILABLE',marketStory:'Không tạo số giả khi dữ liệu nến hợp lệ chưa sẵn sàng.',entry:null,sl:null,tp1:null,tp2:null,tp3:null,failedChecks:['ANALYSIS_DATA_UNAVAILABLE'],checks:null};
        continue;
      }"""
w=rep(w,old_no,new_no,'watch ideal fallback')

# Normal conditional/active Watch outputs explicitly state they are Watch projections only.
old_proj="styles[style]={state:assessment.ok?'TRADEABLE_NOW':'CONDITIONAL_WAIT',...signalWatchProjection(refreshed),failedChecks:assessment.failed,checks:assessment.checks};"
new_proj="styles[style]={state:assessment.ok?'TRADEABLE_NOW':'CONDITIONAL_WAIT',...signalWatchProjection(refreshed),watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false,failedChecks:assessment.failed,checks:assessment.checks};"
w=rep(w,old_proj,new_proj,'watch projection isolation')

# Standardized Stable100 endpoint: never return incompatible cache. Add integrity endpoint.
old_route="if(url.pathname==='/v3/crypto/stable100'&&req.method==='GET'){const cached=await readStable100(env);if(cached)return json({ok:true,...cached});const snap=await loadCryptoSnapshot(env),rows=await persistStable100(env,snap,snap.rows);return json({ok:true,version:V3_VERSION,provider:snap.provider,receivedAt:snap.receivedAt,refreshedAt:nowIso(),target:STABLE100_SIZE,count:rows.length,symbols:rows.map(x=>x.symbol),rows});}"
new_route="if(url.pathname==='/v3/crypto/stable100'&&req.method==='GET'){let cached=await readStable100(env);if(!cached){const snap=await loadCryptoSnapshot(env);await persistStable100(env,snap,snap.rows);cached=await readStable100(env);}if(cached)return json({ok:true,...cached,integrity:stable100Integrity(cached)});return json({ok:false,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,error:'NO_VALID_STANDARDIZED_STABLE100'},503);}\n    if(url.pathname==='/v3/data-integrity'&&req.method==='GET'){const p=await readStable100(env),audit=stable100Integrity(p);return json({ok:audit.ok,version:V3_VERSION,schemaVersion:CRYPTO_DATA_SCHEMA,normalizationVersion:CRYPTO_NORMALIZATION_VERSION,stable100:p?{count:p.count,target:p.target,provider:p.provider,providers:p.providers,refreshedAt:p.refreshedAt,complete:p.complete}:null,problems:audit.problems});}"
w=rep(w,old_route,new_route,'stable100 integrity route')

# Policy wording carries the canonical schema guarantees forward.
w=w.replace("stableUniversePolicy:'TOP_100_STABLE_USDT_PERP_DYNAMIC'","stableUniversePolicy:'TOP_100_STANDARDIZED_CRYPTO_USDT_PERP_DYNAMIC'",1)
w=w.replace("continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES'","continuousRefill:'TARGET_10_SCALP_5_SWING_FROM_HOT_SPARES',dataSchema:'CRYPTO_MARKET_ROW_V3',cacheCompatibility:'VERSION_SCHEMA_NORMALIZATION_STRICT'",1)

# -----------------------------------------------------------------------------
# Android Watchlist: clearly differentiate ideal study plans from active signals.
# -----------------------------------------------------------------------------
a=a.replace('WATCHLIST • TÌM & PHÂN TÍCH COIN','WATCHLIST • LỆNH LÝ TƯỞNG • THAM KHẢO')
a=a.replace('Tìm coin theo mã • không chiếm 15 slot tín hiệu chính','Luôn hiển thị Entry/SL/TP tham khảo khi dữ liệu hợp lệ • không chiếm 15 slot')
a=a.replace('if(x.equals("CONDITIONAL_WAIT")||x.equals("DATA_UNAVAILABLE"))return YELLOW;','if(x.equals("CONDITIONAL_WAIT")||x.equals("IDEAL_REFERENCE")||x.equals("DATA_UNAVAILABLE"))return YELLOW;')
a=a.replace('case "CONDITIONAL_WAIT"->"CHỜ ĐIỀU KIỆN";','case "CONDITIONAL_WAIT"->"CHỜ ĐIỀU KIỆN";\n   case "IDEAL_REFERENCE"->"LỆNH LÝ TƯỞNG";')
old_line='double e=x.optDouble("entry",0),sl=x.optDouble("sl",0),tp=x.optDouble("tp3",0);\n if(e>0&&sl>0&&tp>0)c.addView(tv("Entry "+fmt(e)+"  •  SL "+fmt(sl)+"  •  TP3 "+fmt(tp),9,TEXT,true));'
new_line='double e=x.optDouble("entry",0),sl=x.optDouble("sl",0),tp1=x.optDouble("tp1",0),tp2=x.optDouble("tp2",0),tp=x.optDouble("tp3",0);\n if(e>0&&sl>0&&tp>0){c.addView(tv("Entry "+fmt(e)+"  •  SL "+fmt(sl),9,TEXT,true));c.addView(tv("TP1 "+fmt(tp1)+"  •  TP2 "+fmt(tp2)+"  •  TP3 "+fmt(tp),9,GREEN,true));}\n if(state.equals("IDEAL_REFERENCE")){double d=x.optDouble("distanceToEntryPct",-1);c.addView(tv("THAM KHẢO • KHÔNG PHẢI LỆNH ACTIVE"+(d>=0?"  •  CÁCH ENTRY "+String.format(java.util.Locale.US,"%.2f%%",d):""),8,YELLOW,true));}'
if old_line not in a: raise SystemExit('watch price line missing')
a=a.replace(old_line,new_line,1)
# Ideal reference story should be visible.
a=a.replace('state.equals("TRADEABLE_NOW")||state.equals("ACTIVE_SIGNAL")||state.equals("CONDITIONAL_WAIT")','state.equals("TRADEABLE_NOW")||state.equals("ACTIVE_SIGNAL")||state.equals("CONDITIONAL_WAIT")||state.equals("IDEAL_REFERENCE")',1)

# Release notes marker.
marker="'V3.20.1 normalizes OKX swap base-currency 24h volume into quote-USDT turnover before liquidity ranking, preventing tiny-price high-token-count markets from being falsely ranked as the deepest markets.',"
if marker in w:
    w=w.replace(marker,"'V3.21 namespaces and validates Stable100 cache by worker version, market-row schema and normalization version; incompatible or stale snapshots are never silently served after an update.',\n    'V3.21 composes the crypto universe across Bybit, OKX and Binance, excludes tokenized TradFi/metals, and stamps every Stable100 row with canonical schema, venue, quality tier and quote-turnover normalization metadata.',\n    'V3.21 Watchlist always returns a structurally calculated ideal LIMIT/STOP reference when valid live ticker+candle data are available; these study-only plans never consume an active slot or performance history.',\n    "+marker,1)

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.21 standardized data + ideal Watchlist')
