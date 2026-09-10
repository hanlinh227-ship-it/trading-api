from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
api=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
gradle=Path('signalhub-android/app/build.gradle')

w=worker.read_text();a=activity.read_text();c=api.read_text();g=gradle.read_text()

def block(text,start,end,replacement,name):
    i=text.find(start); assert i>=0,f'{name}: start missing'
    j=text.find(end,i); assert j>i,f'{name}: end missing'
    return text[:i]+replacement+text[j:]

# Identity
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.8','SIGNALHUB-V3-GATEWAY-3.22.9')
w=w.replace("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_21';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_22';")
w=w.replace('versionCode: 37,','versionCode: 38,').replace("versionName: '3.22.8'","versionName: '3.22.9'")
w=w.replace("title: 'SignalHub 3.22.8 Safety-First Market Gate'","title: 'SignalHub 3.22.9 Per-Coin Live Guard'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.8-Safety-First-Market-Gate'","artifactName: 'SignalHub-Android-v3.22.9-Per-Coin-Live-Guard'")
needle='  notes: [\n';assert needle in w
w=w.replace(needle,needle+"    'V3.22.9 tracks freshness per coin, not only per transport. SCALP, SWING and Watchlist expose quote timestamp/age/state and never treat an aged cached price as LIVE.',\n    'V3.22.9 keeps the last displayed price only as a visibly STALE fallback; stale prices are not used as proof that a signal is healthy or newly tradeable.',\n    'V3.22.9 audits Watchlist live coverage against Stable100 and active-signal quote coverage against the realtime Durable Object feed.',\n",1)

# Shared freshness contract.
anchor="const CRYPTO_CACHE_MS = 1500;\n"
assert anchor in w
w=w.replace(anchor,anchor+"const CRYPTO_QUOTE_LIVE_MS = 5000;\nconst CRYPTO_QUOTE_STALE_MS = 15000;\n",1)

# Decorate every ticker row with its own observed freshness.
tickers=r'''async function cryptoTickers(url,env){
  const snap=await loadCryptoSnapshot(env),limit=Math.min(1000,Math.max(1,Number(url.searchParams.get('limit')||1000))),receivedAt=snap.receivedAt||nowIso(),receivedMs=Date.parse(receivedAt),ageMs=Number.isFinite(receivedMs)?Math.max(0,Date.now()-receivedMs):999999,transportLive=snap.live!==false&&ageMs<=CRYPTO_QUOTE_LIVE_MS;
  const rows=(snap.rows||[]).slice(0,limit).map(q=>({...q,quoteReceivedAt:receivedAt,quoteAgeMs:ageMs,quoteState:transportLive?'LIVE':ageMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE',live:transportLive,staleFallback:snap.staleFallback===true}));
  if(transportLive){const stub=mt5LiveStub(env);if(stub){try{await stub.fetch('https://mt5-live/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market:'CRYPTO',rows:snap.rows,receivedAt})});}catch{}}}
  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:transportLive,staleFallback:snap.staleFallback===true,ageMs,count:snap.rows.length,tickers:rows,exchangeTime:snap.exchangeTime,receivedAt,providerErrors:snap.errors||[],freshnessPolicy:{liveMs:CRYPTO_QUOTE_LIVE_MS,staleMs:CRYPTO_QUOTE_STALE_MS,scope:'PER_SYMBOL_OBSERVED_AT_SNAPSHOT'},note:'Every ticker carries quoteReceivedAt/quoteAgeMs/quoteState. A last-good snapshot may remain visible, but it is never labeled LIVE.'});
}
'''
w=block(w,'async function cryptoTickers(url,env){','async function cryptoDiscovery(url,env){',tickers,'cryptoTickers')

# Active realtime quote packet: freshness is carried on every symbol.
old="liveQuotes.push({signalId:String(s.signalId||s.id||''),symbol:canonical(s.symbol),style:String(s.style||'').toUpperCase(),provider,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),receivedAt:snap.receivedAt||at});"
new="const quoteAt=snap.receivedAt||at,quoteMs=Date.parse(quoteAt),quoteAgeMs=Number.isFinite(quoteMs)?Math.max(0,Date.now()-quoteMs):999999,quoteState=snap.live!==false&&quoteAgeMs<=CRYPTO_QUOTE_LIVE_MS?'LIVE':quoteAgeMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE';liveQuotes.push({signalId:String(s.signalId||s.id||''),symbol:canonical(s.symbol),style:String(s.style||'').toUpperCase(),provider,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),quoteReceivedAt:quoteAt,quoteAgeMs,quoteState,live:quoteState==='LIVE'});"
assert old in w,'active quote push marker missing';w=w.replace(old,new,1)

# live-active endpoint reports stale/missing coverage truthfully instead of only pack-level health.
old="if(url.pathname==='/v3/crypto/live-active'&&req.method==='GET'){const pack=await cryptoLiveSnapshot(env);return json({ok:pack.ok!==false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',...pack});}"
new="if(url.pathname==='/v3/crypto/live-active'&&req.method==='GET'){const pack=await cryptoLiveSnapshot(env),portfolio=await realtimePortfolioSnapshot(env),rows=(pack.quotes||[]),fresh=rows.filter(q=>String(q.quoteState||'').toUpperCase()==='LIVE'&&Number(q.lastPrice)>0),activeTotal=Number(portfolio.activeTotal||0),missing=Math.max(0,activeTotal-fresh.length);return json({ok:pack.ok!==false&&missing===0,version:V3_VERSION,mode:'CRYPTO_PER_COIN_LIVE_GUARD',...pack,activeTotal,freshQuoteCount:fresh.length,missingFreshQuotes:missing,allActiveFresh:missing===0,freshnessPolicy:{liveMs:CRYPTO_QUOTE_LIVE_MS,staleMs:CRYPTO_QUOTE_STALE_MS}});}"
assert old in w,'live-active route marker missing';w=w.replace(old,new,1)

# Watch analysis gets explicit quote freshness and refuses to label stale analysis live.
old="const primary=await loadWatchSnapshot(env),resolved=await findWatchTickerMulti(symbol,primary,env),snap=resolved.snap||primary,ticker=resolved.ticker,fresh=snap?.live!==false;"
new="const primary=await loadWatchSnapshot(env),resolved=await findWatchTickerMulti(symbol,primary,env),snap=resolved.snap||primary,ticker=resolved.ticker,quoteAt=snap?.receivedAt||null,quoteMs=Date.parse(quoteAt||''),quoteAgeMs=Number.isFinite(quoteMs)?Math.max(0,Date.now()-quoteMs):999999,fresh=snap?.live!==false&&quoteAgeMs<=CRYPTO_QUOTE_LIVE_MS;"
assert old in w,'watch freshness marker missing';w=w.replace(old,new,1)
old="const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null};"
new="const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null,quoteReceivedAt:quoteAt,quoteAgeMs,quoteState:fresh?'LIVE':quoteAgeMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE',live:fresh};"
assert old in w,'watch baseTicker marker missing';w=w.replace(old,new,1)
w=w.replace("dataHealth:{state:'STALE',live:false,staleFallback:true,receivedAt:snap.receivedAt||null,provider:baseTicker.provider}","dataHealth:{state:quoteAgeMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE',live:false,staleFallback:true,receivedAt:quoteAt,quoteAgeMs,provider:baseTicker.provider}",1)
w=w.replace("dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:snap.receivedAt||null,provider:baseTicker.provider,providerErrors:snap.errors||[]}","dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:quoteAt,quoteAgeMs,provider:baseTicker.provider,providerErrors:snap.errors||[]}",1)

# Status advertises per-symbol freshness guard.
w=w.replace("marketReadVersion:'V3228_SAFETY_FIRST_CURRENT_MARKET_GATE'","marketReadVersion:'V3229_SAFETY_FIRST_PER_COIN_LIVE_GUARD'")
w=w.replace("watchMode:'STABLE100_TAP_FOR_IDEAL_PLAN'","watchMode:'STABLE100_PER_COIN_LIVE_GUARD_TAP_FOR_IDEAL_PLAN'")

# Android: track freshness by signal and by symbol.
a=a.replace('APP_VERSION="3.22.8"','APP_VERSION="3.22.9"')
old='private final Map<String,Long> cryptoSignalPriceAt=new ConcurrentHashMap<>();'
new=old+'\n    private final Map<String,Long> cryptoSymbolPriceAt=new ConcurrentHashMap<>();\n    private final Map<String,String> cryptoSignalQuoteState=new ConcurrentHashMap<>();\n    private final Map<String,String> cryptoSymbolQuoteState=new ConcurrentHashMap<>();'
assert old in a;a=a.replace(old,new,1)

# websocket per-signal freshness, never refresh timestamp from an aged frame.
old='for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:now);}}'
new='for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId",""),sym=x.optString("symbol",""),qs=x.optString("quoteState","LIVE").toUpperCase(Locale.US);long qa=parseMs(x.optString("quoteReceivedAt",p.optString("receivedAt","")));if(qa<=0)qa=received>0?received:now;double px=x.optDouble("lastPrice",0);if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,qa);cryptoSignalQuoteState.put(id,qs);}if(!sym.isEmpty()&&px>0){try{JSONObject qr=new JSONObject();qr.put("symbol",sym);qr.put("lastPrice",px);qr.put("provider",x.optString("provider",cryptoProvider));qr.put("quoteReceivedAt",x.optString("quoteReceivedAt",p.optString("receivedAt","")));qr.put("quoteState",qs);cryptoPrices.put(sym,qr);}catch(Throwable ignored){}cryptoSymbolPriceAt.put(sym,qa);cryptoSymbolQuoteState.put(sym,qs);}}'
assert old in a,'stream loop marker missing';a=a.replace(old,new,1)

# REST refresh tracks observed timestamp for every symbol and does not call an aged snapshot LIVE.
old='Map<String,JSONObject> next=new ConcurrentHashMap<>();if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject q=arr.optJSONObject(i);if(q!=null&&q.optDouble("lastPrice",0)>0)next.put(q.optString("symbol",""),q);}if(!next.isEmpty()){cryptoPrices.clear();cryptoPrices.putAll(next);}cryptoProvider=p.optString("provider",cryptoProvider);cryptoState=p.optBoolean("live",true)?"LIVE":"DELAYED";cryptoCount=p.optInt("count",next.size());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;'
new='Map<String,JSONObject> next=new ConcurrentHashMap<>();long snapAt=parseMs(p.optString("receivedAt",""));if(snapAt<=0)snapAt=System.currentTimeMillis();if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject q=arr.optJSONObject(i);if(q!=null&&q.optDouble("lastPrice",0)>0){String sym=q.optString("symbol","");long qa=parseMs(q.optString("quoteReceivedAt",p.optString("receivedAt","")));if(qa<=0)qa=snapAt;String qs=q.optString("quoteState",p.optBoolean("live",false)?"LIVE":"DELAYED").toUpperCase(Locale.US);next.put(sym,q);cryptoSymbolPriceAt.put(sym,qa);cryptoSymbolQuoteState.put(sym,qs);}}if(!next.isEmpty()){cryptoPrices.clear();cryptoPrices.putAll(next);}cryptoProvider=p.optString("provider",cryptoProvider);long age=Math.max(0,System.currentTimeMillis()-snapAt);cryptoState=p.optBoolean("live",false)&&age<5000?"LIVE":age<15000?"DELAYED":"STALE";cryptoCount=p.optInt("count",next.size());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;'
assert old in a,'REST ticker marker missing';a=a.replace(old,new,1)

# Price can remain visible as last-known, but per-coin state is explicit and health UI no longer inherits global LIVE.
old='private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");long now=System.currentTimeMillis(),streamAge=cryptoStreamLastMs==0?-1:now-cryptoStreamLastMs,restAge=cryptoLastOkMs==0?-1:now-cryptoLastOkMs;String transport=streamAge>=0&&streamAge<5000?"STREAM":"REST FALLBACK";long age=transport.equals("STREAM")?streamAge:restAge;return cryptoProvider+" • "+cryptoState+" • "+transport+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}'
new='private String coinLiveState(JSONObject s){String id=s.optString("signalId",s.optString("id","")),sym=s.optString("symbol","");long now=System.currentTimeMillis();Long at=cryptoSignalPriceAt.get(id);String qs=cryptoSignalQuoteState.get(id);if(at==null){at=cryptoSymbolPriceAt.get(sym);qs=cryptoSymbolQuoteState.get(sym);}if(at==null)return "NO DATA";long age=Math.max(0,now-at);if(age<5000&&"LIVE".equalsIgnoreCase(qs==null?"LIVE":qs))return "LIVE";if(age<15000)return "DELAYED";return "STALE";}\n    private long coinQuoteAge(JSONObject s){String id=s.optString("signalId",s.optString("id","")),sym=s.optString("symbol","");Long at=cryptoSignalPriceAt.get(id);if(at==null)at=cryptoSymbolPriceAt.get(sym);return at==null?Long.MAX_VALUE:Math.max(0,System.currentTimeMillis()-at);}\n    private String sourceText(JSONObject s){String state=coinLiveState(s);long age=coinQuoteAge(s);String provider=s.optString("executionPriceAuthority",s.optString("provider",cryptoProvider));return provider+" • "+state+(age==Long.MAX_VALUE?"":" • "+String.format(Locale.US,"%.1fs",age/1000.0))+(state.equals("LIVE")?" • STREAM/REST FRESH":" • GIÁ CUỐI, KHÔNG COI LÀ LIVE");}\n    private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");long age=cryptoLastOkMs==0?-1:System.currentTimeMillis()-cryptoLastOkMs;return cryptoProvider+" • "+cryptoState+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}'
assert old in a,'sourceText marker missing';a=a.replace(old,new,1)
a=a.replace('TextView sv=tv(sourceText(market),9,stateColor(cryptoState),true);','String coinState=coinLiveState(s);TextView sv=tv(sourceText(s),9,stateColor(coinState),true);',1)
a=a.replace('TextView sv=sourceViews.get(id);if(sv!=null){String state=cryptoState;sv.setText(sourceText(m));sv.setTextColor(stateColor(state));}','TextView sv=sourceViews.get(id);if(sv!=null&&s!=null){String state=coinLiveState(s);sv.setText(sourceText(s));sv.setTextColor(stateColor(state));}',1)

# Watchlist cards and detail show freshness for that exact coin.
old='LinearLayout q=column();q.setGravity(Gravity.END);TextView pv=tv(fmt(px),13,CYAN,true);pv.setGravity(Gravity.END);q.addView(pv);watchUniversePriceViews.put(sym,pv);TextView mv=tv(String.format(Locale.US,"%+.2f%% • %.1fbps",move,spread),8,move>=0?GREEN:RED,true);'
new='LinearLayout q=column();q.setGravity(Gravity.END);Long qa=cryptoSymbolPriceAt.get(sym);long qage=qa==null?Long.MAX_VALUE:Math.max(0,System.currentTimeMillis()-qa);String qstate=qage<5000&&"LIVE".equalsIgnoreCase(cryptoSymbolQuoteState.getOrDefault(sym,"LIVE"))?"LIVE":qage<15000?"DELAYED":"STALE";TextView pv=tv(fmt(px),13,qstate.equals("LIVE")?CYAN:YELLOW,true);pv.setGravity(Gravity.END);q.addView(pv);watchUniversePriceViews.put(sym,pv);TextView fresh=tv(qstate+(qage==Long.MAX_VALUE?"":" • "+String.format(Locale.US,"%.1fs",qage/1000.0)),8,stateColor(qstate),true);fresh.setGravity(Gravity.END);q.addView(fresh);TextView mv=tv(String.format(Locale.US,"%+.2f%% • %.1fbps",move,spread),8,move>=0?GREEN:RED,true);'
assert old in a,'watch card marker missing';a=a.replace(old,new,1)

old='hero.addView(tv(fmt(px),25,CYAN,true));hero.addView(tv("Lệnh dưới đây là kế hoạch tham khảo; Watch không chiếm 10 SCALP + 5 SWING active.",9,MUTED,false));'
new='hero.addView(tv(fmt(px),25,CYAN,true));Long qAt=cryptoSymbolPriceAt.get(sym);long qAge=qAt==null?Long.MAX_VALUE:Math.max(0,System.currentTimeMillis()-qAt);String qState=qAge<5000&&"LIVE".equalsIgnoreCase(cryptoSymbolQuoteState.getOrDefault(sym,"LIVE"))?"LIVE":qAge<15000?"DELAYED":"STALE";hero.addView(tv("GIÁ "+qState+(qAge==Long.MAX_VALUE?"":" • "+String.format(Locale.US,"%.1fs",qAge/1000.0)),10,stateColor(qState),true));hero.addView(tv(qState.equals("LIVE")?"Giá coin này đang cập nhật mới.":"Giá đang trễ; Watch không coi dữ liệu này là live và không dùng để xác nhận entry mới.",9,qState.equals("LIVE")?GREEN:YELLOW,false));hero.addView(tv("Watch chỉ tham khảo và không chiếm slot active.",9,MUTED,false));'
assert old in a,'watch hero marker missing';a=a.replace(old,new,1)

# Update watch price color/state instead of silently showing an old number as if live.
old='private void updateWatchUniversePrices(){for(Map.Entry<String,TextView> e:watchUniversePriceViews.entrySet()){JSONObject q=cryptoPrices.get(e.getKey());if(q!=null){double px=q.optDouble("lastPrice",0);if(px>0)e.getValue().setText(fmt(px));}}}'
new='private void updateWatchUniversePrices(){long now=System.currentTimeMillis();for(Map.Entry<String,TextView> e:watchUniversePriceViews.entrySet()){String sym=e.getKey();JSONObject q=cryptoPrices.get(sym);Long at=cryptoSymbolPriceAt.get(sym);long age=at==null?Long.MAX_VALUE:Math.max(0,now-at);String state=age<5000&&"LIVE".equalsIgnoreCase(cryptoSymbolQuoteState.getOrDefault(sym,"LIVE"))?"LIVE":age<15000?"DELAYED":"STALE";if(q!=null){double px=q.optDouble("lastPrice",0);if(px>0)e.getValue().setText(fmt(px));}e.getValue().setTextColor(state.equals("LIVE")?CYAN:YELLOW);}}'
assert old in a,'update watch prices marker missing';a=a.replace(old,new,1)

a=a.replace('subtitle.setText("WATCH • 100 COIN • CHẠM ĐỂ PHÂN TÍCH");','subtitle.setText("WATCH • 100 COIN • PER-COIN LIVE GUARD");',1)

c=c.replace('SignalHub-Android/3.22.8','SignalHub-Android/3.22.9')
g=g.replace('versionCode 37','versionCode 38').replace("versionName '3.22.8'","versionName '3.22.9'")

worker.write_text(w);activity.write_text(a);api.write_text(c);gradle.write_text(g)

assert 'SIGNALHUB-V3-GATEWAY-3.22.9' in w
assert 'CRYPTO_QUOTE_LIVE_MS = 5000' in w
assert 'quoteReceivedAt' in w and 'quoteAgeMs' in w and 'quoteState' in w
assert 'allActiveFresh' in w and 'missingFreshQuotes' in w
assert 'V3229_SAFETY_FIRST_PER_COIN_LIVE_GUARD' in w
assert 'APP_VERSION="3.22.9"' in a and 'cryptoSymbolPriceAt' in a and 'coinLiveState' in a
assert 'GIÁ CUỐI, KHÔNG COI LÀ LIVE' in a
assert 'PER-COIN LIVE GUARD' in a
assert 'SignalHub-Android/3.22.9' in c
assert 'versionCode 38' in g and "versionName '3.22.9'" in g
print('patched SignalHub V3.22.9 per-coin live guard')
