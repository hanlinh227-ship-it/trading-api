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

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
w=w.replace('SIGNALHUB-V3-GATEWAY-3.22.8','SIGNALHUB-V3-GATEWAY-3.22.9')
w=w.replace("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_21';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_22';")
w=w.replace('versionCode: 37,','versionCode: 38,').replace("versionName: '3.22.8'","versionName: '3.22.9'")
w=w.replace("title: 'SignalHub 3.22.8 Safety-First Market Gate'","title: 'SignalHub 3.22.9 Per-Coin Live Guard'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.8-Safety-First-Market-Gate'","artifactName: 'SignalHub-Android-v3.22.9-Per-Coin-Live-Guard'")
needle='  notes: [\n'; assert needle in w
w=w.replace(needle,needle+"    'V3.22.9 verifies freshness per coin across SCALP, SWING and Watchlist instead of relying on one global connection badge.',\n    'A last-known price may remain visible for continuity, but after 5 seconds it is no longer LIVE and after 15 seconds it is STALE; stale data cannot validate a new signal or health decision.',\n    'Active-signal realtime packets expose per-symbol quote timestamp, age and state. Missing or stale active quotes make allActiveFresh false instead of silently freezing.',\n",1)

anchor='const CRYPTO_CACHE_MS = 1500;\n'; assert anchor in w
w=w.replace(anchor,anchor+'const CRYPTO_QUOTE_LIVE_MS = 5000;\nconst CRYPTO_QUOTE_STALE_MS = 15000;\n',1)

# ---------------------------------------------------------------------------
# Every live-universe row carries freshness metadata.
# ---------------------------------------------------------------------------
tickers=r'''async function cryptoTickers(url,env){
  const snap=await loadCryptoSnapshot(env),limit=Math.min(1000,Math.max(1,Number(url.searchParams.get('limit')||1000))),receivedAt=snap.receivedAt||nowIso(),receivedMs=Date.parse(receivedAt),ageMs=Number.isFinite(receivedMs)?Math.max(0,Date.now()-receivedMs):999999,transportLive=snap.live!==false&&ageMs<=CRYPTO_QUOTE_LIVE_MS;
  const quoteState=transportLive?'LIVE':ageMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE';
  const rows=(snap.rows||[]).slice(0,limit).map(q=>({...q,quoteReceivedAt:receivedAt,quoteAgeMs:ageMs,quoteState,live:transportLive,staleFallback:snap.staleFallback===true}));
  if(transportLive){const stub=mt5LiveStub(env);if(stub){try{await stub.fetch('https://mt5-live/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market:'CRYPTO',rows:snap.rows,receivedAt})});}catch{}}}
  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:transportLive,staleFallback:snap.staleFallback===true,ageMs,count:snap.rows.length,tickers:rows,exchangeTime:snap.exchangeTime,receivedAt,providerErrors:snap.errors||[],freshnessPolicy:{liveMs:CRYPTO_QUOTE_LIVE_MS,staleMs:CRYPTO_QUOTE_STALE_MS,scope:'PER_SYMBOL_OBSERVED_AT_SNAPSHOT'},note:'Each ticker is stamped with the time this provider snapshot was observed. Old last-good data is never labelled LIVE.'});
}
'''
w=block(w,'async function cryptoTickers(url,env){','async function cryptoDiscovery(url,env){',tickers,'cryptoTickers')

# ---------------------------------------------------------------------------
# Durable Object monitor: every active signal gets its own fresh quote row.
# Preserve healthState and never run the health evaluator on stale provider data.
# ---------------------------------------------------------------------------
monitor=r'''  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg),previous=(await this.state.storage.get('cryptoMonitorStatus'))||{},cycle=Number(previous.cycle||0)+1,at=nowIso();
    if(!active.length){
      const status={ok:true,running:false,cycle,activeCrypto:0,underfilledStyles:['SWING','SCALP'],liveSignalQuotes:0,freshSignalQuotes:0,missingFreshQuotes:0,allActiveFresh:true,receivedAt:at};
      await this.state.storage.put('cryptoMonitorStatus',status);const pack={type:'crypto_quotes',ok:true,receivedAt:at,quotes:[],count:0,activeTotal:0,freshQuoteCount:0,missingFreshQuotes:0,allActiveFresh:true};await this.state.storage.put('cryptoLiveQuotes',pack);this.broadcast(pack);return status;
    }
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[],liveQuotes=[];let quotes=0;
    for(const provider of providers){
      try{
        const snap=await cryptoSnapshotForProvider(this.env,provider),quoteAt=snap.receivedAt||at,quoteMs=Date.parse(quoteAt),quoteAgeMs=Number.isFinite(quoteMs)?Math.max(0,Date.now()-quoteMs):999999,providerFresh=snap.live!==false&&quoteAgeMs<=CRYPTO_QUOTE_LIVE_MS;
        if(!providerFresh||!snap.rows?.length){errors.push(`${provider}:${providerFresh?'NO_ROWS':'STALE_OR_OFFLINE'}`);continue;}
        quotes+=snap.rows.length;const by=new Map((snap.rows||[]).map(q=>[canonical(q.symbol),q]));
        for(const s of active){
          const authority=String(s.executionPriceAuthority||s.provider||s.exchange||'BYBIT').toUpperCase();if(authority!==provider)continue;const q=by.get(canonical(s.symbol));if(!q)continue;
          liveQuotes.push({signalId:String(s.signalId||s.id||''),symbol:canonical(s.symbol),style:String(s.style||'').toUpperCase(),provider,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),healthState:s.healthState||'HEALTHY',quoteReceivedAt:quoteAt,quoteAgeMs,quoteState:'LIVE',live:true});
        }
        events.push(...await this.evaluate('CRYPTO',snap.rows,quoteAt));
      }catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}
    }
    const activeNow=this.activeRows(await this.registry()),activeIds=new Set(activeNow.map(s=>String(s.signalId||s.id||''))),freshRows=liveQuotes.filter(q=>activeIds.has(String(q.signalId||''))&&q.live===true&&q.quoteState==='LIVE'&&Number(q.lastPrice)>0),missingFreshQuotes=Math.max(0,activeNow.length-freshRows.length),allActiveFresh=missingFreshQuotes===0;
    const quotePack={type:'crypto_quotes',ok:allActiveFresh,receivedAt:at,count:liveQuotes.length,quotes:liveQuotes,providers,errors,activeTotal:activeNow.length,freshQuoteCount:freshRows.length,missingFreshQuotes,allActiveFresh,freshnessPolicy:{liveMs:CRYPTO_QUOTE_LIVE_MS,staleMs:CRYPTO_QUOTE_STALE_MS}};await this.state.storage.put('cryptoLiveQuotes',quotePack);this.broadcast(quotePack);
    const underfilledStyles=['SWING','SCALP'].filter(st=>activeNow.filter(x=>String(x.style||'').toUpperCase()===st).length<styleTarget(st)),status={ok:errors.length<providers.length&&allActiveFresh,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,liveSignalQuotes:liveQuotes.length,freshSignalQuotes:freshRows.length,missingFreshQuotes,allActiveFresh,events:events.length,healthEvents:events.filter(x=>String(x.type||'').startsWith('HEALTH_')).length,autoCuts:events.filter(x=>x.type==='AUTO_CUT').length,underfilledStyles,refillRequested:underfilledStyles.length>0,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});if(underfilledStyles.length)this.broadcast({type:'book_refill_needed',styles:underfilledStyles,receivedAt:at});return status;
  }
'''
w=block(w,'  async cryptoMonitorCycle(){','  async alarm(){',monitor,'cryptoMonitorCycle')

# ---------------------------------------------------------------------------
# REST active-quote endpoint recomputes age NOW. A stored packet cannot remain
# falsely LIVE just because it was fresh when written.
# ---------------------------------------------------------------------------
old="if(url.pathname==='/v3/crypto/live-active'&&req.method==='GET'){const pack=await cryptoLiveSnapshot(env);return json({ok:pack.ok!==false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',...pack});}"
assert old in w,'live-active route missing'
new="if(url.pathname==='/v3/crypto/live-active'&&req.method==='GET'){const pack=await cryptoLiveSnapshot(env),portfolio=await realtimePortfolioSnapshot(env),now=Date.now(),rows=(pack.quotes||[]).map(q=>{const t=Date.parse(q.quoteReceivedAt||pack.receivedAt||''),age=Number.isFinite(t)?Math.max(0,now-t):999999,state=age<=CRYPTO_QUOTE_LIVE_MS&&q.live!==false?'LIVE':age<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE';return {...q,quoteAgeMs:age,quoteState:state,live:state==='LIVE'};}),activeTotal=Number(portfolio.activeTotal||0),fresh=rows.filter(q=>q.live===true&&Number(q.lastPrice)>0),missing=Math.max(0,activeTotal-fresh.length),allActiveFresh=missing===0;return json({ok:pack.ok!==false&&allActiveFresh,version:V3_VERSION,mode:'CRYPTO_PER_COIN_LIVE_GUARD',...pack,quotes:rows,count:rows.length,activeTotal,freshQuoteCount:fresh.length,missingFreshQuotes:missing,allActiveFresh,freshnessPolicy:{liveMs:CRYPTO_QUOTE_LIVE_MS,staleMs:CRYPTO_QUOTE_STALE_MS}});}"
w=w.replace(old,new,1)

# ---------------------------------------------------------------------------
# Watch detail must use fresh ticker data for THIS coin. Cached ticker can stay
# visible but cannot be considered LIVE/tradeable.
# ---------------------------------------------------------------------------
old="const primary=await loadWatchSnapshot(env),resolved=await findWatchTickerMulti(symbol,primary,env),snap=resolved.snap||primary,ticker=resolved.ticker,fresh=snap?.live!==false;"
assert old in w,'watch freshness marker missing'
new="const primary=await loadWatchSnapshot(env),resolved=await findWatchTickerMulti(symbol,primary,env),snap=resolved.snap||primary,ticker=resolved.ticker,quoteAt=snap?.receivedAt||null,quoteMs=Date.parse(quoteAt||''),quoteAgeMs=Number.isFinite(quoteMs)?Math.max(0,Date.now()-quoteMs):999999,fresh=snap?.live!==false&&quoteAgeMs<=CRYPTO_QUOTE_LIVE_MS;"
w=w.replace(old,new,1)
old="const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null};"
assert old in w,'watch base ticker missing'
new="const baseTicker={lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null,quoteReceivedAt:quoteAt,quoteAgeMs,quoteState:fresh?'LIVE':quoteAgeMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE',live:fresh};"
w=w.replace(old,new,1)
w=w.replace("dataHealth:{state:'STALE',live:false,staleFallback:true,receivedAt:snap.receivedAt||null,provider:baseTicker.provider}","dataHealth:{state:quoteAgeMs<=CRYPTO_QUOTE_STALE_MS?'DELAYED':'STALE',live:false,staleFallback:true,receivedAt:quoteAt,quoteAgeMs,provider:baseTicker.provider}",1)
w=w.replace("dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:snap.receivedAt||null,provider:baseTicker.provider,providerErrors:snap.errors||[]}","dataHealth:{state:'LIVE',live:true,staleFallback:false,receivedAt:quoteAt,quoteAgeMs,provider:baseTicker.provider,providerErrors:snap.errors||[]}",1)
w=w.replace("marketReadVersion:'V3228_SAFETY_FIRST_CURRENT_MARKET_GATE'","marketReadVersion:'V3229_SAFETY_FIRST_PER_COIN_LIVE_GUARD'")
w=w.replace("watchMode:'STABLE100_TAP_FOR_IDEAL_PLAN'","watchMode:'STABLE100_PER_COIN_LIVE_GUARD_TAP_FOR_IDEAL_PLAN'")

# ---------------------------------------------------------------------------
# Android per-coin freshness storage
# ---------------------------------------------------------------------------
a=a.replace('APP_VERSION="3.22.8"','APP_VERSION="3.22.9"')
marker='private final Map<String,Long> cryptoSignalPriceAt=new ConcurrentHashMap<>();'
assert marker in a
replacement=marker+'\n    private final Map<String,Long> cryptoSymbolPriceAt=new ConcurrentHashMap<>();\n    private final Map<String,String> cryptoSignalQuoteState=new ConcurrentHashMap<>();\n    private final Map<String,String> cryptoSymbolQuoteState=new ConcurrentHashMap<>();'
a=a.replace(marker,replacement,1)

# Whole WebSocket consumer replacement: current quote timestamp is preserved,
# and a stale packet cannot refresh the coin's freshness clock.
consume=r'''    private void consumeCryptoStream(String text){
        try{
            JSONObject p=new JSONObject(text);String type=p.optString("type","");
            if("signal_event".equals(type)){JSONObject sig=p.optJSONObject("signal");String ev=p.optString("event","");if(sig!=null)applyRealtimeSignal(sig);if(ev.equals("AUTO_CUT")||ev.equals("TP")||ev.equals("SL")||ev.equals("CANCELLED"))io.execute(()->{try{ApiClient.get("/v3/status?appRefill="+System.currentTimeMillis());}catch(Throwable ignored){}});return;}
            if(!"crypto_quotes".equals(type))return;
            JSONArray q=p.optJSONArray("quotes");if(q==null)return;long now=System.currentTimeMillis(),frameAt=parseMs(p.optString("receivedAt",""));
            for(int i=0;i<q.length();i++){
                JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId",""),sym=x.optString("symbol",""),qs=x.optString("quoteState","LIVE").toUpperCase(Locale.US);long qa=parseMs(x.optString("quoteReceivedAt",p.optString("receivedAt","")));if(qa<=0)qa=frameAt>0?frameAt:now;double px=x.optDouble("lastPrice",0);
                if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,qa);cryptoSignalQuoteState.put(id,qs);}
                if(!sym.isEmpty()&&px>0){try{JSONObject r=new JSONObject();r.put("symbol",sym);r.put("lastPrice",px);r.put("bid",x.optDouble("bid",0));r.put("ask",x.optDouble("ask",0));r.put("spreadBps",x.optDouble("spreadBps",0));r.put("provider",x.optString("provider",cryptoProvider));r.put("quoteReceivedAt",x.optString("quoteReceivedAt",p.optString("receivedAt","")));r.put("quoteState",qs);cryptoPrices.put(sym,r);}catch(Throwable ignored){}cryptoSymbolPriceAt.put(sym,qa);cryptoSymbolQuoteState.put(sym,qs);}
            }
            cryptoStreamLastMs=now;cryptoLastOkMs=now;lastApiOkMs=now;long frameAge=frameAt<=0?Long.MAX_VALUE:Math.max(0,now-frameAt);cryptoState=frameAge<5000?"LIVE":frameAge<15000?"DELAYED":"STALE";
            main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("WATCH"))updateWatchUniversePrices();});
        }catch(Throwable ignored){}
    }

'''
a=block(a,'    private void consumeCryptoStream(String text){','    private void refreshCryptoLive(){',consume,'consumeCryptoStream')

# Whole REST watchdog replacement. Active pack is fetched frequently; full
# universe is fetched while Watch is visible or every ~5s. Each symbol keeps
# the provider observation time instead of assigning System.currentTimeMillis.
refresh=r'''    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{boolean activeOk=false;try{
        long now=System.currentTimeMillis();
        try{
            JSONObject live=new JSONObject(ApiClient.getLive("/v3/crypto/live-active?mobile="+now));JSONArray q=live.optJSONArray("quotes");long frameAt=parseMs(live.optString("receivedAt",""));
            if(q!=null){for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId",""),sym=x.optString("symbol",""),qs=x.optString("quoteState","STALE").toUpperCase(Locale.US);long qa=parseMs(x.optString("quoteReceivedAt",live.optString("receivedAt","")));if(qa<=0)qa=frameAt;double px=x.optDouble("lastPrice",0);if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,qa);cryptoSignalQuoteState.put(id,qs);}if(!sym.isEmpty()&&px>0){cryptoSymbolPriceAt.put(sym,qa);cryptoSymbolQuoteState.put(sym,qs);}}}
            activeOk=live.optBoolean("allActiveFresh",q==null||q.length()==0);if(activeOk){cryptoLastOkMs=now;lastApiOkMs=now;}
        }catch(Throwable ignored){}
        if(screen.equals("WATCH")||cryptoPrices.isEmpty()||now-cryptoUniverseLastMs>5000){
            try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000&mobile="+now));JSONArray arr=p.optJSONArray("tickers");Map<String,JSONObject> next=new ConcurrentHashMap<>();long snapAt=parseMs(p.optString("receivedAt",""));if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject z=arr.optJSONObject(i);if(z==null||z.optDouble("lastPrice",0)<=0)continue;String sym=z.optString("symbol","");long qa=parseMs(z.optString("quoteReceivedAt",p.optString("receivedAt","")));if(qa<=0)qa=snapAt;String qs=z.optString("quoteState",p.optBoolean("live",false)?"LIVE":"STALE").toUpperCase(Locale.US);next.put(sym,z);cryptoSymbolPriceAt.put(sym,qa);cryptoSymbolQuoteState.put(sym,qs);}if(!next.isEmpty()){cryptoPrices.clear();cryptoPrices.putAll(next);cryptoUniverseLastMs=now;}cryptoProvider=p.optString("provider",cryptoProvider);cryptoCount=p.optInt("count",next.size());long age=snapAt<=0?Long.MAX_VALUE:Math.max(0,now-snapAt);cryptoState=p.optBoolean("live",false)&&age<5000?"LIVE":age<15000?"DELAYED":"STALE";if(p.optBoolean("live",false)){cryptoLastOkMs=now;lastApiOkMs=now;}}catch(Throwable ignored){}
        }
        if(!activeOk&&cryptoState.equals("LIVE")){/* universe can be live while an active provider path is degraded; per-coin badges remain authoritative */}
    }catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;cryptoState=age<5000?"DELAYED":age<15000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("WATCH"))updateWatchUniversePrices();});}});}

'''
a=block(a,'    private void refreshCryptoLive(){','    private void updateConnectionViews(){',refresh,'refreshCryptoLive')

# Per-signal coin state helpers. Last known prices can display, but stale is
# explicit and does not inherit the global transport's LIVE badge.
source=r'''    private String coinLiveState(JSONObject s){String id=s.optString("signalId",s.optString("id","")),sym=s.optString("symbol","");Long at=cryptoSignalPriceAt.get(id);String qs=cryptoSignalQuoteState.get(id);if(at==null){at=cryptoSymbolPriceAt.get(sym);qs=cryptoSymbolQuoteState.get(sym);}if(at==null||at<=0)return "NO DATA";long age=Math.max(0,System.currentTimeMillis()-at);if(age<5000&&"LIVE".equalsIgnoreCase(qs==null?"LIVE":qs))return "LIVE";if(age<15000)return "DELAYED";return "STALE";}
    private long coinQuoteAge(JSONObject s){String id=s.optString("signalId",s.optString("id","")),sym=s.optString("symbol","");Long at=cryptoSignalPriceAt.get(id);if(at==null)at=cryptoSymbolPriceAt.get(sym);return at==null||at<=0?Long.MAX_VALUE:Math.max(0,System.currentTimeMillis()-at);}
    private String sourceText(JSONObject s){String state=coinLiveState(s);long age=coinQuoteAge(s);String provider=s.optString("executionPriceAuthority",s.optString("provider",cryptoProvider));return provider+" • "+state+(age==Long.MAX_VALUE?"":" • "+String.format(Locale.US,"%.1fs",age/1000.0))+(state.equals("LIVE")?" • FRESH":" • GIÁ CUỐI, KHÔNG COI LÀ LIVE");}
    private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");long age=cryptoLastOkMs==0?-1:System.currentTimeMillis()-cryptoLastOkMs;return cryptoProvider+" • "+cryptoState+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}

'''
a=block(a,'    private String sourceText(String market){','    private String lifecycleVi(JSONObject s){',source,'source helpers')

# Detail source badge uses exact signal freshness.
a=a.replace('TextView sv=tv(sourceText(market),9,stateColor(cryptoState),true);','String coinState=coinLiveState(s);TextView sv=tv(sourceText(s),9,stateColor(coinState),true);',1)
a=a.replace('TextView sv=sourceViews.get(id);if(sv!=null){String state=cryptoState;sv.setText(sourceText(m));sv.setTextColor(stateColor(state));}','TextView sv=sourceViews.get(id);if(sv!=null&&s!=null){String state=coinLiveState(s);sv.setText(sourceText(s));sv.setTextColor(stateColor(state));}',1)

# Watch cards: keep numeric last-known value, but freshness is visible per coin.
old='LinearLayout q=column();q.setGravity(Gravity.END);TextView pv=tv(fmt(px),13,CYAN,true);pv.setGravity(Gravity.END);q.addView(pv);watchUniversePriceViews.put(sym,pv);TextView mv=tv(String.format(Locale.US,"%+.2f%% • %.1fbps",move,spread),8,move>=0?GREEN:RED,true);'
assert old in a,'watch card price marker missing'
new='LinearLayout q=column();q.setGravity(Gravity.END);Long qa=cryptoSymbolPriceAt.get(sym);long qage=qa==null?Long.MAX_VALUE:Math.max(0,System.currentTimeMillis()-qa);String qstate=qage<5000&&"LIVE".equalsIgnoreCase(cryptoSymbolQuoteState.getOrDefault(sym,"LIVE"))?"LIVE":qage<15000?"DELAYED":"STALE";TextView pv=tv(fmt(px),13,qstate.equals("LIVE")?CYAN:YELLOW,true);pv.setGravity(Gravity.END);q.addView(pv);watchUniversePriceViews.put(sym,pv);TextView fresh=tv(qstate+(qage==Long.MAX_VALUE?"":" • "+String.format(Locale.US,"%.1fs",qage/1000.0)),8,stateColor(qstate),true);fresh.setGravity(Gravity.END);q.addView(fresh);TextView mv=tv(String.format(Locale.US,"%+.2f%% • %.1fbps",move,spread),8,move>=0?GREEN:RED,true);'
a=a.replace(old,new,1)

old='hero.addView(tv(fmt(px),25,CYAN,true));hero.addView(tv("Lệnh dưới đây là kế hoạch tham khảo; Watch không chiếm 10 SCALP + 5 SWING active.",9,MUTED,false));'
if old not in a:
    old='hero.addView(tv(fmt(px),25,CYAN,true));hero.addView(tv("Lệnh dưới đây là kế hoạch tham khảo; Watch không chiếm 5 SCALP + 2 SWING active.",9,MUTED,false));'
assert old in a,'watch hero marker missing'
new='hero.addView(tv(fmt(px),25,CYAN,true));Long qAt=cryptoSymbolPriceAt.get(sym);long qAge=qAt==null?Long.MAX_VALUE:Math.max(0,System.currentTimeMillis()-qAt);String qState=qAge<5000&&"LIVE".equalsIgnoreCase(cryptoSymbolQuoteState.getOrDefault(sym,"LIVE"))?"LIVE":qAge<15000?"DELAYED":"STALE";hero.addView(tv("GIÁ "+qState+(qAge==Long.MAX_VALUE?"":" • "+String.format(Locale.US,"%.1fs",qAge/1000.0)),10,stateColor(qState),true));hero.addView(tv(qState.equals("LIVE")?"Coin này đang có quote mới.":"Quote coin này đang trễ; Watch không dùng giá này để xác nhận entry mới.",9,qState.equals("LIVE")?GREEN:YELLOW,false));hero.addView(tv("Watch chỉ tham khảo và không chiếm slot active.",9,MUTED,false));'
a=a.replace(old,new,1)

old='private void updateWatchUniversePrices(){for(Map.Entry<String,TextView> e:watchUniversePriceViews.entrySet()){JSONObject q=cryptoPrices.get(e.getKey());if(q!=null){double px=q.optDouble("lastPrice",0);if(px>0)e.getValue().setText(fmt(px));}}}'
assert old in a,'updateWatchUniversePrices marker missing'
new='private void updateWatchUniversePrices(){long now=System.currentTimeMillis();for(Map.Entry<String,TextView> e:watchUniversePriceViews.entrySet()){String sym=e.getKey();JSONObject q=cryptoPrices.get(sym);Long at=cryptoSymbolPriceAt.get(sym);long age=at==null?Long.MAX_VALUE:Math.max(0,now-at);String state=age<5000&&"LIVE".equalsIgnoreCase(cryptoSymbolQuoteState.getOrDefault(sym,"LIVE"))?"LIVE":age<15000?"DELAYED":"STALE";if(q!=null){double px=q.optDouble("lastPrice",0);if(px>0)e.getValue().setText(fmt(px));}e.getValue().setTextColor(state.equals("LIVE")?CYAN:YELLOW);}}'
a=a.replace(old,new,1)
a=a.replace('subtitle.setText("WATCH • 100 COIN • CHẠM ĐỂ PHÂN TÍCH");','subtitle.setText("WATCH • 100 COIN • PER-COIN LIVE GUARD");',1)

# Android / API version
c=c.replace('SignalHub-Android/3.22.8','SignalHub-Android/3.22.9')
g=g.replace('versionCode 37','versionCode 38').replace("versionName '3.22.8'","versionName '3.22.9'")

worker.write_text(w);activity.write_text(a);api.write_text(c);gradle.write_text(g)

# Source contracts
assert 'SIGNALHUB-V3-GATEWAY-3.22.9' in w
assert "const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_22';" in w
assert 'CRYPTO_QUOTE_LIVE_MS = 5000' in w and 'CRYPTO_QUOTE_STALE_MS = 15000' in w
assert 'quoteReceivedAt' in w and 'quoteAgeMs' in w and 'quoteState' in w
assert 'allActiveFresh' in w and 'missingFreshQuotes' in w
assert 'healthState:s.healthState' in w
assert 'V3229_SAFETY_FIRST_PER_COIN_LIVE_GUARD' in w
assert 'APP_VERSION="3.22.9"' in a and 'cryptoSymbolPriceAt' in a and 'coinLiveState' in a
assert 'GIÁ CUỐI, KHÔNG COI LÀ LIVE' in a and 'PER-COIN LIVE GUARD' in a
assert 'SignalHub-Android/3.22.9' in c
assert 'versionCode 38' in g and "versionName '3.22.9'" in g
print('patched SignalHub V3.22.9 per-coin live guard R2')
