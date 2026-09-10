from pathlib import Path

worker=Path('signalhub-worker/gateway-v3.js')
activity=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
api=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
monitor=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
gradle=Path('signalhub-android/app/build.gradle')

w=worker.read_text(); a=activity.read_text(); c=api.read_text(); m=monitor.read_text(); g=gradle.read_text()

# ---------------- BACKEND V3.22.5 ----------------
w=w.replace("SIGNALHUB-V3-GATEWAY-3.22.4","SIGNALHUB-V3-GATEWAY-3.22.5")
w=w.replace("versionName: '3.22.4'","versionName: '3.22.5'")
w=w.replace("title: 'SignalHub 3.22.4 Responsive Style Target Read'","title: 'SignalHub 3.22.5 Realtime Unique Book'")
w=w.replace("artifactName: 'SignalHub-Android-v3.22.4-Responsive-Style-Target-Read'","artifactName: 'SignalHub-Android-v3.22.5-Realtime-Unique-Book'")

old="""  portfolioFrom(reg){
    const active=this.activeRows(reg),counts={FOREX:0,CRYPTO:0},styles={SCALP:0,SWING:0};
    for(const s of active){const m=String(s.market||'').toUpperCase(),st=String(s.style||'').toUpperCase();if(m in counts)counts[m]++;if(st in styles)styles[st]++;}
    return {activeTotal:active.length,counts,styles,uniqueSymbols:new Set(active.map(x=>`${String(x.market||'').toUpperCase()}:${canonical(x.symbol)}`)).size,policy:PORTFOLIO_POLICY};
  }"""
new="""  portfolioFrom(reg){
    const active=this.activeRows(reg),counts={FOREX:0,CRYPTO:0},styles={SCALP:0,SWING:0},orderTypes={SCALP:{MARKET:0,LIMIT:0,STOP:0},SWING:{MARKET:0,LIMIT:0,STOP:0}},symbolCounts={};
    for(const s of active){const m=String(s.market||'').toUpperCase(),st=String(s.style||'').toUpperCase(),ot=String(s.orderType||'MARKET').toUpperCase(),sym=canonical(s.symbol);if(m in counts)counts[m]++;if(st in styles)styles[st]++;if(orderTypes[st]&&ot in orderTypes[st])orderTypes[st][ot]++;if(sym)symbolCounts[sym]=(symbolCounts[sym]||0)+1;}
    const duplicateSymbols=Object.entries(symbolCounts).filter(([,n])=>n>1).map(([symbol])=>symbol),uniqueSymbols=Object.keys(symbolCounts).length;
    return {activeTotal:active.length,counts,styles,orderTypes,uniqueSymbols,duplicateSymbols,exactTarget:styles.SCALP===10&&styles.SWING===5&&active.length===15&&uniqueSymbols===15&&duplicateSymbols.length===0,policy:PORTFOLIO_POLICY};
  }"""
assert old in w, 'portfolioFrom marker changed'
w=w.replace(old,new,1)

old="""  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    const previous=(await this.state.storage.get('cryptoMonitorStatus'))||{},cycle=Number(previous.cycle||0)+1,at=nowIso();
    if(!active.length){const status={ok:true,running:false,cycle,activeCrypto:0,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);return status;}
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[];let quotes=0;
    for(const provider of providers){
      try{const snap=await cryptoSnapshotForProvider(this.env,provider);if(snap.live===false||!snap.rows?.length){errors.push(`${provider}:NO_LIVE_ROWS`);continue;}quotes+=snap.rows.length;events.push(...await this.evaluate('CRYPTO',snap.rows,snap.receivedAt||at));}
      catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}
    }
    const depleted=[...new Set(events.filter(e=>['CANCELLED','TP','SL'].includes(String(e?.type||''))).map(e=>String(e?.signal?.style||'').toUpperCase()).filter(x=>['SCALP','SWING'].includes(x)))],replacements=[];
    for(const style of depleted){const r=await this.promoteStandby(style,'LIFECYCLE_EVENT');if(r?.promoted?.length)replacements.push({style,...r});}
    const activeNow=this.activeRows(await this.registry()),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,events:events.length,replacements,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;
  }"""
new="""  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    const previous=(await this.state.storage.get('cryptoMonitorStatus'))||{},cycle=Number(previous.cycle||0)+1,at=nowIso();
    if(!active.length){const status={ok:true,running:false,cycle,activeCrypto:0,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);const pack={type:'crypto_quotes',ok:true,receivedAt:at,quotes:[],count:0};await this.state.storage.put('cryptoLiveQuotes',pack);this.broadcast(pack);return status;}
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[],liveQuotes=[];let quotes=0;
    for(const provider of providers){
      try{
        const snap=await cryptoSnapshotForProvider(this.env,provider);if(snap.live===false||!snap.rows?.length){errors.push(`${provider}:NO_LIVE_ROWS`);continue;}quotes+=snap.rows.length;
        const by=new Map((snap.rows||[]).map(q=>[canonical(q.symbol),q]));
        for(const s of active){const authority=String(s.executionPriceAuthority||s.provider||s.exchange||'BYBIT').toUpperCase();if(authority!==provider)continue;const q=by.get(canonical(s.symbol));if(!q)continue;liveQuotes.push({signalId:String(s.signalId||s.id||''),symbol:canonical(s.symbol),style:String(s.style||'').toUpperCase(),provider,lastPrice:Number(q.lastPrice||0),bid:Number(q.bid||0),ask:Number(q.ask||0),spreadBps:Number(q.spreadBps||0),receivedAt:snap.receivedAt||at});}
        events.push(...await this.evaluate('CRYPTO',snap.rows,snap.receivedAt||at));
      }catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}
    }
    const quotePack={type:'crypto_quotes',ok:liveQuotes.length>0,receivedAt:at,count:liveQuotes.length,quotes:liveQuotes,providers,errors};await this.state.storage.put('cryptoLiveQuotes',quotePack);this.broadcast(quotePack);
    const depleted=[...new Set(events.filter(e=>['CANCELLED','TP','SL'].includes(String(e?.type||''))).map(e=>String(e?.signal?.style||'').toUpperCase()).filter(x=>['SCALP','SWING'].includes(x)))],replacements=[];
    for(const style of depleted){const r=await this.promoteStandby(style,'LIFECYCLE_EVENT');if(r?.promoted?.length)replacements.push({style,...r});}
    const activeNow=this.activeRows(await this.registry()),status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:activeNow.length,providers,quotes,liveSignalQuotes:liveQuotes.length,events:events.length,replacements,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;
  }"""
assert old in w, 'cryptoMonitorCycle marker changed'
w=w.replace(old,new,1)

old="try{const quotes=await this.state.storage.get('quotes'),heartbeat=await this.state.storage.get('heartbeat');if(quotes)server.send(JSON.stringify({type:'quotes',...quotes,heartbeat:heartbeat||null}));}catch{}"
new="try{const quotes=await this.state.storage.get('quotes'),heartbeat=await this.state.storage.get('heartbeat'),crypto=await this.state.storage.get('cryptoLiveQuotes');if(quotes)server.send(JSON.stringify({type:'quotes',...quotes,heartbeat:heartbeat||null}));if(crypto)server.send(JSON.stringify(crypto));}catch{}"
assert old in w, 'websocket initial snapshot marker changed'
w=w.replace(old,new,1)

old="if(req.method==='GET'&&url.pathname==='/crypto-monitor-status'){const status=(await this.state.storage.get('cryptoMonitorStatus'))||{ok:true,running:false,cycle:0};return new Response(JSON.stringify(status),{headers:{'content-type':'application/json'}});}"
new="if(req.method==='GET'&&url.pathname==='/crypto-monitor-status'){const status=(await this.state.storage.get('cryptoMonitorStatus'))||{ok:true,running:false,cycle:0};return new Response(JSON.stringify(status),{headers:{'content-type':'application/json'}});}\n    if(req.method==='GET'&&url.pathname==='/crypto-live-snapshot'){const pack=(await this.state.storage.get('cryptoLiveQuotes'))||{type:'crypto_quotes',ok:false,receivedAt:null,count:0,quotes:[]};return new Response(JSON.stringify(pack),{headers:{'content-type':'application/json','cache-control':'no-store'}});}"
assert old in w, 'DO monitor status route marker changed'
w=w.replace(old,new,1)

marker="async function cryptoServerMonitorStatus(env){const stub=mt5LiveStub(env);if(!stub)return {ok:false,running:false};try{const r=await stub.fetch('https://mt5-live/crypto-monitor-status');return r.ok?await r.json():{ok:false,running:false};}catch(e){return {ok:false,running:false,error:String(e?.message||e)};}}"
assert marker in w, 'cryptoServerMonitorStatus marker missing'
insert=marker+"\nasync function cryptoLiveSnapshot(env){const stub=mt5LiveStub(env);if(!stub)return {type:'crypto_quotes',ok:false,receivedAt:null,count:0,quotes:[]};try{const r=await stub.fetch('https://mt5-live/crypto-live-snapshot');return r.ok?await r.json():{type:'crypto_quotes',ok:false,receivedAt:null,count:0,quotes:[]};}catch(e){return {type:'crypto_quotes',ok:false,receivedAt:null,count:0,quotes:[],error:String(e?.message||e)};}}"
w=w.replace(marker,insert,1)

old="rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);\n  const targetActive=styleTarget(style);"
new="rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status);\n  const targetActive=styleTarget(style);\n  if(status==='active'){const seen=new Set();rows=rows.filter(s=>{const sym=canonical(s.symbol);if(!sym||seen.has(sym))return false;seen.add(sym);return true;}).slice(0,Math.min(limit,targetActive));}else rows=rows.slice(0,limit);"
assert old in w, 'unifiedSignals active filter marker changed'
w=w.replace(old,new,1)

old="let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').slice(0,limit);"
new="let refreshed=await getV31Signals(env,market,style);refreshed=refreshed.map(x=>normalizeDisplaySignal(x,market,style));const seen=new Set();rows=refreshed.filter(s=>s.status==='PENDING'||s.status==='OPEN').filter(s=>{const sym=canonical(s.symbol);if(!sym||seen.has(sym))return false;seen.add(sym);return true;}).slice(0,Math.min(limit,targetActive));"
assert old in w, 'unifiedSignals refreshed filter marker changed'
w=w.replace(old,new,1)

old="if(url.pathname==='/v3/crypto/monitor'&&req.method==='GET'){const kick=url.searchParams.get('kick')==='1'?await kickCryptoServerMonitor(env):null;if(ctx?.waitUntil)ctx.waitUntil(Promise.resolve(cryptoOnlyMaintenance(env)).catch(()=>{}));return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',status:await cryptoServerMonitorStatus(env),kick,portfolio:await realtimePortfolioSnapshot(env)});}"
new=old+"\n    if(url.pathname==='/v3/crypto/stream'&&req.method==='GET')return mt5Stream(req,env);\n    if(url.pathname==='/v3/crypto/live-active'&&req.method==='GET'){const pack=await cryptoLiveSnapshot(env);return json({ok:pack.ok!==false,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',...pack});}"
assert old in w, 'crypto monitor worker route marker changed'
w=w.replace(old,new,1)

needle="  notes: [\n"
if 'V3.22.5 streams provider-pinned live quotes' not in w:
    w=w.replace(needle,needle+"    'V3.22.5 streams provider-pinned live quotes for every active crypto signal from the same 1-second server monitor that drives LIMIT/STOP activation and TP/SL lifecycle.',\n    'V3.22.5 hardens the active book contract to exactly 10 SCALP + 5 SWING maximum slots across MARKET/LIMIT/STOP with atomic cross-style symbol uniqueness and app-facing deduplication.',\n",1)

# ---------------- ANDROID NETWORK ----------------
c='''package com.hanlinh.signalhub;\n\nimport java.io.IOException;\nimport java.util.concurrent.TimeUnit;\n\nimport okhttp3.ConnectionPool;\nimport okhttp3.OkHttpClient;\nimport okhttp3.Request;\nimport okhttp3.Response;\nimport okhttp3.ResponseBody;\nimport okhttp3.WebSocket;\nimport okhttp3.WebSocketListener;\n\npublic final class ApiClient {\n    public static final String BASE_URL = "https://signalhub-forex.hanlinh227.workers.dev";\n\n    private static final ConnectionPool POOL = new ConnectionPool(10, 5, TimeUnit.MINUTES);\n    private static final OkHttpClient API_CLIENT = new OkHttpClient.Builder()\n            .connectionPool(POOL).connectTimeout(4,TimeUnit.SECONDS).readTimeout(7,TimeUnit.SECONDS)\n            .callTimeout(9,TimeUnit.SECONDS).retryOnConnectionFailure(true).build();\n    private static final OkHttpClient LIVE_CLIENT = new OkHttpClient.Builder()\n            .connectionPool(POOL).connectTimeout(2,TimeUnit.SECONDS).readTimeout(3,TimeUnit.SECONDS)\n            .callTimeout(4,TimeUnit.SECONDS).pingInterval(10,TimeUnit.SECONDS)\n            .retryOnConnectionFailure(true).build();\n\n    private ApiClient() {}\n\n    public static WebSocket connectCryptoStream(WebSocketListener listener) {\n        String ws = BASE_URL.replace("https://","wss://").replace("http://","ws://") + "/v3/crypto/stream";\n        Request r = new Request.Builder().url(ws).header("Cache-Control","no-cache").header("User-Agent","SignalHub-Android/3.22.5").build();\n        return LIVE_CLIENT.newWebSocket(r, listener);\n    }\n\n    public static String get(String path) throws Exception { return getInternal(path,false); }\n    public static String getLive(String path) throws Exception { return getInternal(path,true); }\n\n    private static String getInternal(String path, boolean live) throws Exception {\n        String url = path.startsWith("http") ? path : BASE_URL + path;\n        OkHttpClient client = live ? LIVE_CLIENT : API_CLIENT;\n        IOException last = null;\n        for(int attempt=0; attempt<2; attempt++) {\n            Request req = new Request.Builder().url(url).get()\n                    .header("Accept","application/json")\n                    .header("Cache-Control","no-cache, no-store")\n                    .header("Pragma","no-cache")\n                    .header("User-Agent","SignalHub-Android/3.22.5")\n                    .build();\n            try(Response resp = client.newCall(req).execute()) {\n                ResponseBody body = resp.body();\n                String text = body == null ? "" : body.string();\n                if(!resp.isSuccessful()) throw new RuntimeException("HTTP " + resp.code() + ": " + text);\n                return text;\n            } catch(IOException e) {\n                last=e;\n                if(attempt==0) try { Thread.sleep(120L); } catch(InterruptedException ie) { Thread.currentThread().interrupt(); throw ie; }\n            }\n        }\n        throw last == null ? new IOException("request failed") : last;\n    }\n}\n'''

# ---------------- ANDROID ACTIVITY ----------------
a=a.replace('APP_VERSION="3.22.4"','APP_VERSION="3.22.5"')
a=a.replace('private static final long LIVE_REFRESH_MS=500L; // REST fallback; WebSocket is primary','private static final long LIVE_REFRESH_MS=750L; // crypto WebSocket primary; REST watchdog fallback')
old='private final Map<String,JSONObject> cryptoPrices=new ConcurrentHashMap<>();'
new=old+'\n    private final Map<String,Double> cryptoSignalPrices=new ConcurrentHashMap<>();\n    private final Map<String,Long> cryptoSignalPriceAt=new ConcurrentHashMap<>();'
assert old in a;a=a.replace(old,new,1)
old='private volatile long fxStreamLastMs=0,watchLastBulkMs=0,watchLastRenderMs=0;\n    private WebSocket fxSocket;'
new='private volatile long fxStreamLastMs=0,cryptoStreamLastMs=0,lastCryptoStreamConnectAttemptMs=0,watchLastBulkMs=0,watchLastRenderMs=0;\n    private WebSocket fxSocket,cryptoSocket;'
assert old in a;a=a.replace(old,new,1)
old='@Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);main.removeCallbacks(loop);main.post(loop);}'
new='@Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);ensureCryptoStream();main.removeCallbacks(loop);main.post(loop);}'
assert old in a;a=a.replace(old,new,1)
old='@Override protected void onDestroy(){main.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}'
new='@Override protected void onDestroy(){main.removeCallbacksAndMessages(null);closeCryptoStream();io.shutdownNow();super.onDestroy();}'
assert old in a;a=a.replace(old,new,1)
old='refreshCryptoLive();\n        long now=System.currentTimeMillis();'
new='long now=System.currentTimeMillis();\n        ensureCryptoStream();\n        if(cryptoStreamLastMs==0||now-cryptoStreamLastMs>2500)refreshCryptoLive();'
assert old in a;a=a.replace(old,new,1)
marker='    private void connectForexStream(){\n'
assert marker in a
methods=r'''    private void ensureCryptoStream(){
        long now=System.currentTimeMillis();
        if(cryptoSocket!=null&&cryptoStreamLastMs>0&&now-cryptoStreamLastMs<=5000)return;
        if(now-lastCryptoStreamConnectAttemptMs<1500)return;
        lastCryptoStreamConnectAttemptMs=now;
        closeCryptoStream();
        try{
            cryptoSocket=ApiClient.connectCryptoStream(new WebSocketListener(){
                @Override public void onOpen(WebSocket webSocket,Response response){cryptoStreamLastMs=System.currentTimeMillis();lastApiOkMs=cryptoStreamLastMs;main.post(()->updateConnectionViews());}
                @Override public void onMessage(WebSocket webSocket,String text){consumeCryptoStream(text);}
                @Override public void onFailure(WebSocket webSocket,Throwable t,Response response){cryptoStreamLastMs=0;cryptoSocket=null;main.post(()->updateConnectionViews());}
                @Override public void onClosed(WebSocket webSocket,int code,String reason){cryptoStreamLastMs=0;cryptoSocket=null;main.post(()->updateConnectionViews());}
            });
        }catch(Throwable ignored){cryptoSocket=null;cryptoStreamLastMs=0;}
    }
    private void closeCryptoStream(){try{if(cryptoSocket!=null)cryptoSocket.close(1000,"activity-destroy");}catch(Throwable ignored){}cryptoSocket=null;}
    private void consumeCryptoStream(String text){
        try{
            JSONObject p=new JSONObject(text);String type=p.optString("type","");
            if("signal_event".equals(type)){JSONObject sig=p.optJSONObject("signal");if(sig!=null)applyRealtimeSignal(sig);return;}
            if(!"crypto_quotes".equals(type))return;
            JSONArray q=p.optJSONArray("quotes");if(q==null)return;long now=System.currentTimeMillis(),received=parseMs(p.optString("receivedAt",""));
            for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:now);}}
            cryptoStreamLastMs=now;cryptoLastOkMs=now;lastApiOkMs=now;cryptoState=(received>0&&now-received>3500)?"DELAYED":"LIVE";
            main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("HOME"))renderHome(false);});
        }catch(Throwable ignored){}
    }

'''
a=a.replace(marker,methods+marker,1)
old='''    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000"));JSONArray a=p.optJSONArray("tickers");cryptoPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null)cryptoPrices.put(q.optString("symbol",""),q);}cryptoProvider=p.optString("provider","CRYPTO");cryptoState=p.optBoolean("live",true)?"LIVE":"DELAYED";cryptoCount=p.optInt("count",a==null?0:a.length());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;}catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;cryptoState=age<10000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);if(screen.equals("WATCH")){updateWatchUniversePrices();}});}});}'''
new='''    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{try{
        try{JSONObject live=new JSONObject(ApiClient.getLive("/v3/crypto/live-active"));JSONArray q=live.optJSONArray("quotes");long received=parseMs(live.optString("receivedAt",""));if(q!=null)for(int i=0;i<q.length();i++){JSONObject x=q.optJSONObject(i);if(x==null)continue;String id=x.optString("signalId","");double px=x.optDouble("lastPrice",0);if(!id.isEmpty()&&px>0){cryptoSignalPrices.put(id,px);cryptoSignalPriceAt.put(id,received>0?received:System.currentTimeMillis());}}}catch(Throwable ignored){}
        JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000"));JSONArray arr=p.optJSONArray("tickers");Map<String,JSONObject> next=new ConcurrentHashMap<>();if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject q=arr.optJSONObject(i);if(q!=null&&q.optDouble("lastPrice",0)>0)next.put(q.optString("symbol",""),q);}if(!next.isEmpty()){cryptoPrices.clear();cryptoPrices.putAll(next);}cryptoProvider=p.optString("provider",cryptoProvider);cryptoState=p.optBoolean("live",true)?"LIVE":"DELAYED";cryptoCount=p.optInt("count",next.size());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;
    }catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;cryptoState=age<5000?"DELAYED":age<15000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);if(screen.equals("WATCH")){updateWatchUniversePrices();}});}});}'''
assert old in a, 'refreshCryptoLive marker changed';a=a.replace(old,new,1)
old='private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol",""),m=s.optString("market","FOREX");if(m.equals("CRYPTO")){String authority=s.optString("executionPriceAuthority",s.optString("provider","")).toUpperCase(Locale.US);if(!authority.isEmpty()&&!authority.equalsIgnoreCase(cryptoProvider))return s.optDouble("lastPrice",fallback);JSONObject q=cryptoPrices.get(sym);return q==null?fallback:q.optDouble("lastPrice",fallback);}Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}'
new='private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol",""),m=s.optString("market","FOREX");if(m.equals("CRYPTO")){String id=s.optString("signalId",s.optString("id",""));Double direct=cryptoSignalPrices.get(id);Long at=cryptoSignalPriceAt.get(id);if(direct!=null&&direct>0&&at!=null&&System.currentTimeMillis()-at<8000)return direct;String authority=s.optString("executionPriceAuthority",s.optString("provider","")).toUpperCase(Locale.US);if(authority.isEmpty()||authority.equalsIgnoreCase(cryptoProvider)){JSONObject q=cryptoPrices.get(sym);if(q!=null&&q.optDouble("lastPrice",0)>0)return q.optDouble("lastPrice",fallback);}double last=s.optDouble("lastPrice",0);return last>0?last:fallback;}Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}'
assert old in a, 'priceFor marker changed';a=a.replace(old,new,1)
old='private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");long age=cryptoLastOkMs==0?-1:System.currentTimeMillis()-cryptoLastOkMs;return cryptoProvider+" • "+cryptoState+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}'
new='private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");long now=System.currentTimeMillis(),streamAge=cryptoStreamLastMs==0?-1:now-cryptoStreamLastMs,restAge=cryptoLastOkMs==0?-1:now-cryptoLastOkMs;String transport=streamAge>=0&&streamAge<5000?"STREAM":"REST FALLBACK";long age=transport.equals("STREAM")?streamAge:restAge;return cryptoProvider+" • "+cryptoState+" • "+transport+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}'
assert old in a, 'sourceText marker changed';a=a.replace(old,new,1)
a=a.replace('subtitle.setText(style+" • CRYPTO REALTIME");','subtitle.setText(style+" • CRYPTO REALTIME • "+(style.equals("SCALP")?"10 SLOT":"5 SLOT"));')

# ---------------- BACKGROUND MONITOR ----------------
m=m.replace('private static final long LOOP_MS=1000L;','private static final long LOOP_MS=2000L;')
m=m.replace('private static final long RECENT_NEW_MS=10*60*1000L;','private static final long RECENT_NEW_MS=10*60*1000L;\n    private static final long REFILL_CHECK_MS=30000L;\n    private long lastRefillCheck=0L;')
m=m.replace('        try{ApiClient.getLive("/v3/crypto/tickers?limit=1000");}catch(Throwable ignored){}\n        int active=0,failed=0;','        int active=0,failed=0;')
old='            if(styleActive==0)try{ApiClient.get("/v3/scan?market=CRYPTO&style="+style);}catch(Throwable ignored){}'
new='            int target="SCALP".equals(style)?10:5;long now=System.currentTimeMillis();if(styleActive<target&&now-lastRefillCheck>=REFILL_CHECK_MS)try{ApiClient.get("/v3/status");}catch(Throwable ignored){}'
assert old in m, 'monitor scan marker changed';m=m.replace(old,new,1)
old='        NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(n!=null){String text=failed==0?"CRYPTO LIVE • "+active+" tín hiệu SCALP/SWING đang theo dõi":"DEGRADED • "+failed+"/2 luồng đang nối lại • "+active+" active";n.notify(FOREGROUND_ID,monitor(text));}'
new='        if(System.currentTimeMillis()-lastRefillCheck>=REFILL_CHECK_MS)lastRefillCheck=System.currentTimeMillis();NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(n!=null){String text=failed==0?"CRYPTO LIVE • "+active+" / 15 active • 10 SCALP + 5 SWING":"DEGRADED • "+failed+"/2 luồng đang nối lại • "+active+" / 15 active";n.notify(FOREGROUND_ID,monitor(text));}'
assert old in m;m=m.replace(old,new,1)
m=m.replace('setContentTitle("SignalHub V3.14 • CRYPTO STABILITY LIVE")','setContentTitle("SignalHub V3.22.5 • CRYPTO REALTIME")')

g=g.replace('versionCode 33','versionCode 34').replace("versionName '3.22.4'","versionName '3.22.5'")

worker.write_text(w); activity.write_text(a); api.write_text(c); monitor.write_text(m); gradle.write_text(g)

assert 'SIGNALHUB-V3-GATEWAY-3.22.5' in w
assert "'/v3/crypto/stream'" in w and "'/v3/crypto/live-active'" in w
assert 'duplicateSymbols' in w and 'exactTarget' in w
assert 'APP_VERSION="3.22.5"' in a and 'connectCryptoStream' in a and 'cryptoSignalPrices' in a
assert 'ConnectionPool(10' in c and 'connectCryptoStream' in c
assert 'LOOP_MS=2000L' in m
assert 'versionCode 34' in g and "versionName '3.22.5'" in g
print('patched SignalHub V3.22.5 realtime unique book')
