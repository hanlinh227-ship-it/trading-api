from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
w=W.read_text(); a=A.read_text()

def rep(text,old,new,label):
    if old not in text:
        raise SystemExit(f'{label}: marker missing')
    return text.replace(old,new,1)

old=r'''async function watchAnalyze(url,env){
  const symbol=normalizeWatchSymbol(url.searchParams.get('symbol')||'');
  if(!symbol)return json({ok:false,version:V3_VERSION,error:'BAD_WATCH_SYMBOL'},400);
  const snap=await loadCryptoSnapshot(env);
  if(snap.live===false)return json({ok:false,version:V3_VERSION,symbol,error:'NO_FRESH_CRYPTO_SNAPSHOT',provider:snap.provider||null},503);
  const ticker=(snap.rows||[]).find(x=>canonical(x.symbol)===symbol);
  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_IN_LIVE_UNIVERSE',provider:snap.provider||null},404);
  const activeBook=await getActiveBook(env),styles={};
  await Promise.all(['SCALP','SWING'].map(async style=>{
    const active=activeBook.find(x=>String(x.style||'').toUpperCase()===style&&canonical(x.symbol)===symbol);
    if(active){styles[style]=watchFlatSignal(active,'ACTIVE_SIGNAL',active.entryAssessment);return;}
    const setup=await analyzeCryptoCandidate(ticker,style);
    if(!setup){styles[style]={state:'NO_TRADE',activeSignal:false,symbol,side:null,orderType:null,status:null,entry:null,sl:null,tp1:null,tp2:null,tp3:null,targetRR:null,marketRegime:'NO_TRADE',marketStory:'Chưa có cấu trúc đủ rõ cho style này ở thời điểm phân tích.',judgment:'NO_TRADE',entryModel:null,coverageTier:null,coverageFallback:false,assessmentMethod:null,failedChecks:['NO_COHERENT_SETUP'],rationale:[],provider:ticker.exchange||snap.provider||null};return;}
    const strict=assessEntrySetup(setup),conditional=setup.coverageFallback?assessCoverageSetup(setup):strict;
    const state=strict.verdict==='PASS'?'TRADEABLE_NOW':conditional.verdict==='PASS'?'CONDITIONAL_WAIT':'NO_TRADE';
    styles[style]=watchFlatSignal(setup,state,state==='TRADEABLE_NOW'?strict:conditional);
  }));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:{lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null},styles,activeBook:{targetScalp:2,targetSwing:2,note:'Watchlist does not consume or replace active slots.'},analyzedAt:nowIso()});
}
'''
new=r'''async function loadWatchSnapshot(env){
  let last=null,lastError=null;
  for(let i=0;i<3;i++){
    try{const snap=await loadCryptoSnapshot(env);last=snap;if(snap?.live!==false&&Array.isArray(snap?.rows)&&snap.rows.length)return snap;}catch(e){lastError=String(e?.message||e);}
    if(i<2)await sleep(250*(i+1));
  }
  if(last)return last;
  return {rows:[],provider:null,live:false,staleFallback:false,receivedAt:null,errors:lastError?[lastError]:['NO_WATCH_SNAPSHOT']};
}
function watchUnavailable(symbol,provider,reason){return {state:'DATA_UNAVAILABLE',activeSignal:false,symbol,side:null,orderType:null,status:null,entry:null,sl:null,tp1:null,tp2:null,tp3:null,targetRR:null,marketRegime:'DATA_UNAVAILABLE',marketStory:'Dữ liệu thị trường tạm thời chưa đủ mới để phân tích an toàn. Không suy diễn tín hiệu từ giá cũ.',judgment:'DATA_UNAVAILABLE',entryModel:null,coverageTier:null,coverageFallback:false,assessmentMethod:null,failedChecks:[reason||'FRESH_DATA_UNAVAILABLE'],rationale:[],provider:provider||null};}
async function watchAnalyze(url,env){
  const symbol=normalizeWatchSymbol(url.searchParams.get('symbol')||'');
  if(!symbol)return json({ok:false,version:V3_VERSION,error:'BAD_WATCH_SYMBOL'},400);
  const snap=await loadWatchSnapshot(env),ticker=(snap.rows||[]).find(x=>canonical(x.symbol)===symbol),fresh=snap.live!==false;
  if(!ticker){
    const unavailable=watchUnavailable(symbol,snap.provider,'SYMBOL_NOT_AVAILABLE_IN_CURRENT_SNAPSHOT');
    return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:null,dataHealth:{state:fresh?'LIVE_SYMBOL_MISSING':'UNAVAILABLE',live:false,staleFallback:snap.staleFallback===true,provider:snap.provider||null,providerErrors:snap.errors||[]},styles:{SCALP:unavailable,SWING:{...unavailable}},activeBook:{targetScalp:2,targetSwing:2,note:'Watchlist does not consume or replace active slots.'},analyzedAt:nowIso()});
  }
  const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null};
  if(!fresh){
    const unavailable=watchUnavailable(symbol,baseTicker.provider,'FRESH_TICKER_UNAVAILABLE');
    return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:baseTicker,dataHealth:{state:'STALE',live:false,staleFallback:true,ageMs:snap.ageMs??null,receivedAt:snap.receivedAt||null,provider:baseTicker.provider,providerErrors:snap.errors||[]},styles:{SCALP:unavailable,SWING:{...unavailable}},activeBook:{targetScalp:2,targetSwing:2,note:'Watchlist does not consume or replace active slots.'},analyzedAt:nowIso()});
  }
  const activeBook=await getActiveBook(env),styles={};
  await Promise.all(['SCALP','SWING'].map(async style=>{
    const active=activeBook.find(x=>String(x.style||'').toUpperCase()===style&&canonical(x.symbol)===symbol);
    if(active){styles[style]=watchFlatSignal(active,'ACTIVE_SIGNAL',active.entryAssessment);return;}
    const setup=await analyzeCryptoCandidate(ticker,style);
    if(!setup){styles[style]={state:'NO_TRADE',activeSignal:false,symbol,side:null,orderType:null,status:null,entry:null,sl:null,tp1:null,tp2:null,tp3:null,targetRR:null,marketRegime:'NO_TRADE',marketStory:'Chưa có cấu trúc đủ rõ cho style này ở thời điểm phân tích.',judgment:'NO_TRADE',entryModel:null,coverageTier:null,coverageFallback:false,assessmentMethod:null,failedChecks:['NO_COHERENT_SETUP'],rationale:[],provider:baseTicker.provider};return;}
    const strict=assessEntrySetup(setup),conditional=setup.coverageFallback?assessCoverageSetup(setup):strict;
    const state=strict.verdict==='PASS'?'TRADEABLE_NOW':conditional.verdict==='PASS'?'CONDITIONAL_WAIT':'NO_TRADE';
    styles[style]=watchFlatSignal(setup,state,state==='TRADEABLE_NOW'?strict:conditional);
  }));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:baseTicker,dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:snap.receivedAt||null,provider:baseTicker.provider,providerErrors:snap.errors||[]},styles,activeBook:{targetScalp:2,targetSwing:2,note:'Watchlist does not consume or replace active slots.'},analyzedAt:nowIso()});
}
'''
w=rep(w,old,new,'watch resilience')
W.write_text(w)

old="private int watchStateColor(String state){String x=state==null?\"\":state.toUpperCase(Locale.US);if(x.equals(\"ACTIVE_SIGNAL\"))return GREEN;if(x.equals(\"TRADEABLE_NOW\"))return CYAN;if(x.equals(\"CONDITIONAL_WAIT\"))return YELLOW;return RED;}"
new="private int watchStateColor(String state){String x=state==null?\"\":state.toUpperCase(Locale.US);if(x.equals(\"ACTIVE_SIGNAL\"))return GREEN;if(x.equals(\"TRADEABLE_NOW\"))return CYAN;if(x.equals(\"CONDITIONAL_WAIT\")||x.equals(\"DATA_UNAVAILABLE\"))return YELLOW;return RED;}"
a=rep(a,old,new,'watch state color')
old="private String watchStateVi(String state){String x=state==null?\"\":state.toUpperCase(Locale.US);return switch(x){case \"ACTIVE_SIGNAL\"->\"CÓ LỆNH\";case \"TRADEABLE_NOW\"->\"SETUP ĐẸP\";case \"CONDITIONAL_WAIT\"->\"CHỜ ĐIỀU KIỆN\";case \"NO_TRADE\"->\"NO TRADE\";default->\"ĐANG PHÂN TÍCH\";};}"
new="private String watchStateVi(String state){String x=state==null?\"\":state.toUpperCase(Locale.US);return switch(x){case \"ACTIVE_SIGNAL\"->\"CÓ LỆNH\";case \"TRADEABLE_NOW\"->\"SETUP ĐẸP\";case \"CONDITIONAL_WAIT\"->\"CHỜ ĐIỀU KIỆN\";case \"DATA_UNAVAILABLE\"->\"DỮ LIỆU TẠM THIẾU\";case \"NO_TRADE\"->\"NO TRADE\";default->\"ĐANG PHÂN TÍCH\";};}"
a=rep(a,old,new,'watch state text')
A.write_text(a)
print('hardened V3.16 watchlist freshness behavior')
