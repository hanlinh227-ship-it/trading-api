from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GW=ROOT/'signalhub-worker/gateway-v3.js'
WR=ROOT/'signalhub-worker/wrangler.jsonc'
ACT=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java'
GR=ROOT/'signalhub-android/app/build.gradle'
MON=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java'


def between(s,start,end,new):
    a=s.index(start); b=s.index(end,a)
    return s[:a]+new+s[b:]

# ---------------- Worker: Durable Object realtime price bus -----------------
g=GW.read_text(encoding='utf-8')
g=g.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.1.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.4.0';")
g=g.replace("versionCode: 8,\n  versionName: '3.2.0',\n  title: 'SignalHub 3.2.0',","versionCode: 10,\n  versionName: '3.4.0',\n  title: 'SignalHub 3.4.0',")
g=g.replace("artifactName: 'SignalHub-Android-v3.1.0',","artifactName: 'SignalHub-Android-v3.4.0',")
if "Realtime Durable Object price bus" not in g:
    g=g.replace("notes: [","notes: [\n    'Realtime Durable Object price bus + WebSocket stream for Exness MT5 quotes.',\n    'LIMIT and STOP pending orders are displayed separately and become LIVE immediately when trigger price is crossed.',")

insert_after="const sleep = ms => new Promise(r => setTimeout(r, ms));\n"
if 'export class MT5LiveState' not in g:
    do_code=r'''

export class MT5LiveState {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.clients = new Set();
  }
  async fetch(req) {
    const url = new URL(req.url);
    if (req.headers.get('Upgrade') === 'websocket') {
      const pair = new WebSocketPair();
      const client = pair[0], server = pair[1];
      server.accept();
      this.clients.add(server);
      const drop = () => this.clients.delete(server);
      server.addEventListener('close', drop);
      server.addEventListener('error', drop);
      try {
        const quotes = await this.state.storage.get('quotes');
        const heartbeat = await this.state.storage.get('heartbeat');
        if (quotes) server.send(JSON.stringify({type:'quotes', ...quotes, heartbeat:heartbeat||null}));
      } catch {}
      return new Response(null, {status:101, webSocket:client});
    }
    if (req.method === 'POST' && url.pathname === '/prices') {
      const packet = await req.json();
      await this.state.storage.put('quotes', packet);
      const msg = JSON.stringify({type:'quotes', ...packet});
      for (const ws of [...this.clients]) {
        try { ws.send(msg); } catch { this.clients.delete(ws); }
      }
      return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt}), {headers:{'content-type':'application/json'}});
    }
    if (req.method === 'POST' && url.pathname === '/heartbeat') {
      const heartbeat = await req.json();
      await this.state.storage.put('heartbeat', heartbeat);
      const msg = JSON.stringify({type:'heartbeat', heartbeat});
      for (const ws of [...this.clients]) {
        try { ws.send(msg); } catch { this.clients.delete(ws); }
      }
      return new Response(JSON.stringify({ok:true,receivedAt:heartbeat.receivedAt}), {headers:{'content-type':'application/json'}});
    }
    if (url.pathname === '/snapshot') {
      const [quotes,heartbeat] = await Promise.all([this.state.storage.get('quotes'),this.state.storage.get('heartbeat')]);
      return new Response(JSON.stringify({ok:!!quotes,quotes:quotes||null,heartbeat:heartbeat||null}), {headers:{'content-type':'application/json','cache-control':'no-store'}});
    }
    return new Response('not found',{status:404});
  }
}
function mt5LiveStub(env){
  if(!env?.MT5_LIVE)return null;
  return env.MT5_LIVE.get(env.MT5_LIVE.idFromName('primary'));
}
async function readMt5Realtime(env){
  const stub=mt5LiveStub(env);
  if(stub){
    try{const r=await stub.fetch('https://mt5-live/snapshot');if(r.ok)return await r.json()}catch{}
  }
  let quotes=null,heartbeat=null;
  try{const raw=await env?.SIGNALS_KV?.get('v3:mt5:quotes:latest');if(raw)quotes=JSON.parse(raw)}catch{}
  try{const raw=await env?.SIGNALS_KV?.get('v3:mt5:heartbeat:latest');if(raw)heartbeat=JSON.parse(raw)}catch{}
  return {ok:!!quotes,quotes,heartbeat};
}
'''
    g=g.replace(insert_after,insert_after+do_code)

start='async function mt5Prices(req, env) {'
end='async function mt5Heartbeat(req,env){'
new=r'''async function mt5Prices(req, env) {
  if (!bridgeAllowed(req,env)) return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  const body=await readJson(req,2_000_000), quotes=(Array.isArray(body?.quotes)?body.quotes:[]).slice(0,120).map(sanitizeQuote).filter(Boolean), receivedAt=nowIso();
  const packet={ok:true,version:V3_VERSION,source:'EXNESS_MT5',bridgeVersion:String(body?.bridgeVersion||''),server:String(body?.server||''),receivedAt,quotes,count:quotes.length};
  const stub=mt5LiveStub(env);
  if(stub){
    const r=await stub.fetch('https://mt5-live/prices',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(packet)});
    if(r.ok)return json({ok:true,accepted:quotes.length,receivedAt,transport:'DURABLE_OBJECT_REALTIME'});
  }
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_REALTIME_STORE'},503);
  await env.SIGNALS_KV.put('v3:mt5:quotes:latest',JSON.stringify(packet),{expirationTtl:MT5_QUOTE_TTL});
  return json({ok:true,accepted:quotes.length,receivedAt,transport:'KV_FALLBACK'});
}
'''
g=between(g,start,end,new)

start='async function mt5Heartbeat(req,env){'
end='async function loadSignalById(kv,id){'
new=r'''async function mt5Heartbeat(req,env){
  if(!bridgeAllowed(req,env))return json({ok:false,error:'MT5_BRIDGE_UNAUTHORIZED'},401);
  const body=await readJson(req),receivedAt=nowIso();
  const heartbeat={bridgeVersion:String(body?.bridgeVersion||''),status:String(body?.status||''),server:String(body?.server||''),company:String(body?.company||''),terminalConnected:body?.terminalConnected===true,tradeAllowed:body?.tradeAllowed===true,resolvedSymbols:Number(body?.resolvedSymbols||0),positions:Number(body?.positions||0),orders:Number(body?.orders||0),queuedEvents:Number(body?.queuedEvents||0),receivedAt};
  const stub=mt5LiveStub(env);
  if(stub){
    const r=await stub.fetch('https://mt5-live/heartbeat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(heartbeat)});
    if(r.ok)return json({ok:true,receivedAt,transport:'DURABLE_OBJECT_REALTIME'});
  }
  if(!env?.SIGNALS_KV)return json({ok:false,error:'NO_REALTIME_STORE'},503);
  await env.SIGNALS_KV.put('v3:mt5:heartbeat:latest',JSON.stringify(heartbeat),{expirationTtl:MT5_HEARTBEAT_TTL});
  return json({ok:true,receivedAt,transport:'KV_FALLBACK'});
}
'''
g=between(g,start,end,new)

start='async function mt5Live(env){'
end='function cleanBybitTicker(x){'
new=r'''async function mt5Live(env){
  const snap=await readMt5Realtime(env),quotes=snap?.quotes||null,heartbeat=snap?.heartbeat||null;
  let lastEvent=null;try{const er=await env?.SIGNALS_KV?.get('v3:mt5:event:latest');if(er)lastEvent=JSON.parse(er)}catch{}
  const qAt=Date.parse(quotes?.receivedAt||''),hAt=Date.parse(heartbeat?.receivedAt||''),quoteAgeMs=Number.isFinite(qAt)?Math.max(0,Date.now()-qAt):null,heartbeatAgeMs=Number.isFinite(hAt)?Math.max(0,Date.now()-hAt):null;
  const terminalConnected=heartbeat?.terminalConnected!==false;
  const state=quoteAgeMs===null?'OFFLINE':!terminalConnected?'OFFLINE':heartbeatAgeMs!==null&&heartbeatAgeMs>10000?'OFFLINE':quoteAgeMs<=1800?'LIVE':quoteAgeMs<=4000?'DELAYED':quoteAgeMs<=10000?'STALE':'OFFLINE';
  return json({ok:!!quotes,version:V3_VERSION,market:'FOREX_EXNESS',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME':'KV_FALLBACK',stream:'/v3/forex/stream',state,quoteAgeMs,heartbeatAgeMs,quotes:quotes?.quotes||[],count:quotes?.count||0,heartbeat,lastEvent:lastEvent?{event:lastEvent.event,signalId:lastEvent.signalId||'',brokerSymbol:lastEvent.brokerSymbol||'',price:num(lastEvent.price),dealReason:lastEvent.dealReason||'',receivedAt:lastEvent.receivedAt}:null},quotes?200:503);
}
async function mt5Stream(req,env){
  const stub=mt5LiveStub(env);if(!stub)return new Response('realtime stream unavailable',{status:503});
  const headers=new Headers(req.headers);headers.set('Upgrade','websocket');
  return stub.fetch(new Request('https://mt5-live/stream',{method:'GET',headers}));
}

'''
g=between(g,start,end,new)

start='async function exnessQuoteMap(env){'
end='async function tvForexSwing(){'
new=r'''async function exnessQuoteMap(env){
  const snap=await readMt5Realtime(env),p=snap?.quotes||null;if(!p)return {map:new Map(),state:'OFFLINE',ageMs:null};
  const ageMs=Math.max(0,Date.now()-Date.parse(p.receivedAt||'')),state=ageMs<=1800?'LIVE':ageMs<=4000?'DELAYED':'STALE',map=new Map((p.quotes||[]).map(q=>[canonical(q.symbol),Number(q.mid)]));return {map,state,ageMs};
}
'''
g=between(g,start,end,new)

start='async function v3Status(env){'
end='async function handleV3(req,env,ctx){'
new=r'''async function v3Status(env){
  const snap=await readMt5Realtime(env),mt5=snap?.heartbeat||null;
  return json({ok:true,version:V3_VERSION,service:'SignalHub multi-market gateway',checkpoint:CHECKPOINT,app:V31_RELEASE,forex:{executionPriceAuthority:'EXNESS_MT5',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME_WEBSOCKET':'KV_FALLBACK',scalp:'LEGACY_2.1_QUALITY_ENGINE',swing:'V31_SEPARATE_1H_4H_1D_ENGINE'},crypto:{priceAuthority:'BYBIT_PREFERRED_WITH_LABELED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'V31_MULTI_TF_ENGINE',swing:'V31_MULTI_TF_ENGINE',antiFomo:true},engines:{forexScalp:'ACTIVE',forexSwing:'ACTIVE_REQUIRES_FRESH_EXNESS',cryptoScalp:'ACTIVE',cryptoSwing:'ACTIVE'},mt5Heartbeat:mt5?{bridgeVersion:mt5.bridgeVersion,terminalConnected:mt5.terminalConnected,tradeAllowed:mt5.tradeAllowed,resolvedSymbols:mt5.resolvedSymbols,receivedAt:mt5.receivedAt}:null,winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'});
}
'''
g=between(g,start,end,new)

g=g.replace("if(url.pathname==='/v3/forex/live'&&req.method==='GET')return mt5Live(env);","if(url.pathname==='/v3/forex/live'&&req.method==='GET')return mt5Live(env);\n    if(url.pathname==='/v3/forex/stream'&&req.method==='GET'&&String(req.headers.get('Upgrade')||'').toLowerCase()==='websocket')return mt5Stream(req,env);")
GW.write_text(g,encoding='utf-8')

w=WR.read_text(encoding='utf-8')
if '"MT5_LIVE"' not in w:
    w=w.replace('  "triggers": {', '  "durable_objects": {\n    "bindings": [\n      { "name": "MT5_LIVE", "class_name": "MT5LiveState" }\n    ]\n  },\n  "migrations": [\n    { "tag": "v34-mt5-live-v1", "new_sqlite_classes": ["MT5LiveState"] }\n  ],\n  "triggers": {')
WR.write_text(w,encoding='utf-8')

# ---------------- Android V3.4 UI + WebSocket -----------------
a=ACT.read_text(encoding='utf-8')
a=a.replace('private static final String APP_VERSION="3.3.0";','private static final String APP_VERSION="3.4.0";')
a=a.replace('private static final long LIVE_REFRESH_MS=500L;','private static final long LIVE_REFRESH_MS=500L; // REST fallback; WebSocket is primary')
if 'import okhttp3.WebSocket;' not in a:
    a=a.replace('import org.json.JSONObject;','import org.json.JSONObject;\n\nimport okhttp3.Response;\nimport okhttp3.WebSocket;\nimport okhttp3.WebSocketListener;')
a=a.replace('private volatile int fxCount=0,cryptoCount=0;','private volatile int fxCount=0,cryptoCount=0;\n    private volatile long fxStreamLastMs=0;\n    private WebSocket fxSocket;')
a=a.replace('if(!resumed)return;\n        refreshForexLive();refreshCryptoLive();','if(!resumed)return;\n        long streamAge=fxStreamLastMs==0?Long.MAX_VALUE:System.currentTimeMillis()-fxStreamLastMs;\n        if(streamAge>1500)refreshForexLive();\n        refreshCryptoLive();')
a=a.replace('@Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);main.removeCallbacks(loop);main.post(loop);}','@Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);connectForexStream();main.removeCallbacks(loop);main.post(loop);}')
a=a.replace('@Override protected void onPause(){resumed=false;main.removeCallbacks(loop);super.onPause();}','@Override protected void onPause(){resumed=false;main.removeCallbacks(loop);closeForexStream();super.onPause();}')

# renderSignals with LIVE and pending boxes
start='    private void renderSignals(boolean animate){'
end='    private String performanceSummary()'
new=r'''    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}
        Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();pnlViews.clear();subtitle.setText("EXNESS REALTIME • LIVE / LIMIT / STOP");
            LinearLayout title=row();title.addView(tv("TÍN HIỆU GIAO DỊCH",16,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));title.addView(chip(style,CYAN));content.addView(title);
            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),pendingRows=new ArrayList<>();
            for(JSONObject s:rows){double px=priceFor(s,s.optDouble("entry",0));if(isDisplayLive(s,px))liveRows.add(s);else pendingRows.add(s);}
            LinearLayout summary=card();summary.addView(tv("LIVE "+liveRows.size()+"   •   LIMIT/STOP "+pendingRows.size(),12,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));summary.addView(tv("LIMIT/STOP tự chuyển sang LIVE ngay khi giá realtime chạm điều kiện kích hoạt.",9,YELLOW,false));content.addView(summary);
            addOrderSection("●  LỆNH LIVE",liveRows,GREEN,"Đã khớp / đang chạy theo giá hiện tại");
            addOrderSection("◷  LỆNH CHỜ • LIMIT / STOP",pendingRows,YELLOW,"Chưa khớp Entry • tách riêng khỏi lệnh đang chạy");
        };if(animate)swap(body);else body.run();updateAllPriceViews();
    }
    private void addOrderSection(String title,List<JSONObject> rows,int color,String sub){
        LinearLayout h=row();TextView t=tv(title,13,color,true);h.addView(t,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(String.valueOf(rows.size()),color));content.addView(h);content.addView(tv(sub,9,MUTED,false));
        if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Không có lệnh trong nhóm này.",10,MUTED,true));content.addView(z);return;}
        for(JSONObject s:rows)content.addView(signalCard(s));
    }

'''
a=between(a,start,end,new)

a=a.replace('meta.addView(tv(signalStyle+" • "+order,10,CYAN,true),new LinearLayout.LayoutParams(0,-2,1f));','meta.addView(tv(signalStyle+" • "+orderDisplay(s,pxForOrder(s)),10,orderColor(s,pxForOrder(s)),true),new LinearLayout.LayoutParams(0,-2,1f));')
# Above references pxForOrder before local px declaration; helper computes itself so okay.
a=a.replace('c.addView(tv(signalStyle+" • "+s.optString("orderType","MARKET")+" • "+lifecycleVi(s),10,CYAN,true));','c.addView(tv(signalStyle+" • "+orderDisplay(s,priceFor(s,s.optDouble("entry",0)))+" • "+lifecycleVi(s),10,orderColor(s,priceFor(s,s.optDouble("entry",0))),true));')

# Home live/pending counts
old='private int activeCount(String st){int n=0;for(JSONObject s:allSignals())if(st==null||st.equals(s.optString("style","")))n++;return n;}'
new='private int activeCount(String st){int n=0;for(JSONObject s:allSignals())if((st==null||st.equals(s.optString("style","")))&&isDisplayLive(s,priceFor(s,s.optDouble("entry",0))))n++;return n;}\n    private int pendingCount(){int n=0;for(JSONObject s:allSignals())if(!isDisplayLive(s,priceFor(s,s.optDouble("entry",0))))n++;return n;}'
a=a.replace(old,new)
a=a.replace('"SCALP + SWING",CYAN','"LIVE • chờ "+pendingCount(),CYAN')
a=a.replace('ui.addView(line("Live refresh","500 ms",GREEN));','ui.addView(line("Forex transport","WebSocket realtime + REST fallback",GREEN));ui.addView(line("Fallback refresh","500 ms",MUTED));')

# Pending/live state helpers + status text
marker='    private String historicalWr(String market,String st)'
helpers=r'''    private double pxForOrder(JSONObject s){return priceFor(s,s.optDouble("entry",0));}
    private boolean pendingTriggered(JSONObject s,double px){
        if(!"PENDING".equalsIgnoreCase(s.optString("status",""))||!(px>0))return false;
        String type=s.optString("orderType","LIMIT").toUpperCase(Locale.US),side=sideVi(s.optString("side",""));double entry=s.optDouble("entry",0);if(!(entry>0))return false;
        if(type.equals("LIMIT"))return side.equals("BUY")?px<=entry:px>=entry;
        if(type.equals("STOP"))return side.equals("BUY")?px>=entry:px<=entry;
        return false;
    }
    private boolean isDisplayLive(JSONObject s,double px){return "OPEN".equalsIgnoreCase(s.optString("status",""))||pendingTriggered(s,px);}
    private String orderDisplay(JSONObject s,double px){if(isDisplayLive(s,px))return "LIVE";String o=s.optString("orderType","MARKET").toUpperCase(Locale.US);return o.equals("LIMIT")?"LIMIT":o.equals("STOP")?"STOP":"MARKET";}
    private int orderColor(JSONObject s,double px){String o=orderDisplay(s,px);return o.equals("LIVE")?GREEN:o.equals("LIMIT")?YELLOW:o.equals("STOP")?BLUE:CYAN;}
    private String pendingDistanceText(JSONObject s,double px){double e=s.optDouble("entry",0),sl=s.optDouble("sl",0);double base=Math.max(Math.abs(e-sl),1e-12),dist=Math.abs(px-e)/base;return s.optString("orderType","LIMIT").toUpperCase(Locale.US)+" • CHỜ KHỚP • cách Entry "+String.format(Locale.US,"%.2fR",dist);}

'''
a=a.replace(marker,helpers+marker)
a=a.replace('private String tradeStatusText(JSONObject s,double px){String life=lifecycleVi(s);if(life.contains("CHỜ"))return "CHỜ ENTRY • giá hiện tại "+fmt(px);','private String tradeStatusText(JSONObject s,double px){if(!isDisplayLive(s,px))return pendingDistanceText(s,px);')
a=a.replace('private int tradeStatusColor(JSONObject s,double px){if(lifecycleVi(s).contains("CHỜ"))return YELLOW;return currentR(s,px)>=0?GREEN:RED;}','private int tradeStatusColor(JSONObject s,double px){if(!isDisplayLive(s,px))return orderColor(s,px);return currentR(s,px)>=0?GREEN:RED;}')

# Lifecycle: immediate UI transition when trigger crossed
old='private String lifecycleVi(JSONObject s){String x=s.optString("lifecycle","").toUpperCase(Locale.US);if(x.isEmpty()){String st=s.optString("status","");if(st.equals("PENDING"))x="PENDING_ENTRY";else if(st.equals("OPEN"))x="ACTIVE";else x=st;}return switch(x){case "PENDING_ENTRY"->"CHỜ ENTRY";case "ACTIVE"->s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP":"ĐANG CHẠY";case "TP1_HIT"->"TP1";case "TP2_HIT"->"TP2";case "TP3_HIT"->"TP ĐẠT";case "STOP_LOSS_HIT"->"SL";case "CANCELLED"->"ĐÃ HỦY";case "EXPIRED"->"HẾT HẠN";default->x.isEmpty()?"WATCHING":x;};}'
new='private String lifecycleVi(JSONObject s){double px=priceFor(s,s.optDouble("entry",0));if(pendingTriggered(s,px))return "ĐÃ KHỚP • LIVE";String x=s.optString("lifecycle","").toUpperCase(Locale.US);if(x.isEmpty()){String st=s.optString("status","");if(st.equals("PENDING"))x="PENDING_ENTRY";else if(st.equals("OPEN"))x="ACTIVE";else x=st;}return switch(x){case "PENDING_ENTRY"->"CHỜ ENTRY";case "ACTIVE"->s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP":"ĐANG CHẠY";case "TP1_HIT"->"TP1";case "TP2_HIT"->"TP2";case "TP3_HIT"->"TP ĐẠT";case "STOP_LOSS_HIT"->"SL";case "CANCELLED"->"ĐÃ HỦY";case "EXPIRED"->"HẾT HẠN";default->x.isEmpty()?"WATCHING":x;};}'
a=a.replace(old,new)

# WebSocket methods before refreshForexLive
marker='    private void refreshForexLive()'
stream_methods=r'''    private void connectForexStream(){
        closeForexStream();
        try{fxSocket=ApiClient.connectForexStream(new WebSocketListener(){
            @Override public void onOpen(WebSocket webSocket,Response response){fxStreamLastMs=System.currentTimeMillis();}
            @Override public void onMessage(WebSocket webSocket,String text){consumeForexStream(text);}
            @Override public void onFailure(WebSocket webSocket,Throwable t,Response response){fxStreamLastMs=0;main.post(()->updateConnectionViews());}
        });}catch(Throwable ignored){fxStreamLastMs=0;}
    }
    private void closeForexStream(){try{if(fxSocket!=null)fxSocket.close(1000,"pause");}catch(Throwable ignored){}fxSocket=null;}
    private void consumeForexStream(String text){
        try{JSONObject p=new JSONObject(text),packet=p;String type=p.optString("type","");if(type.equals("heartbeat")){return;}JSONArray a=packet.optJSONArray("quotes");if(a==null)return;Map<String,Double> next=new ConcurrentHashMap<>();for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null){double mid=q.optDouble("mid",0);if(mid>0)next.put(q.optString("symbol",""),mid);}}if(next.isEmpty())return;fxPrices.clear();fxPrices.putAll(next);fxCount=packet.optInt("count",a.length());long received=parseMs(packet.optString("receivedAt",""));fxQuoteAgeMs=received>0?Math.max(0,System.currentTimeMillis()-received):0;fxState=fxQuoteAgeMs<=1800?"LIVE":fxQuoteAgeMs<=4000?"DELAYED":"STALE";fxStreamLastMs=System.currentTimeMillis();fxLastOkMs=fxStreamLastMs;lastApiOkMs=fxStreamLastMs;main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("HOME"))renderHome(false);});}catch(Throwable ignored){}
    }

'''
a=a.replace(marker,stream_methods+marker)

a=a.replace('fxLive.setText("EXNESS • "+fxState+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.1fs",fxQuoteAgeMs/1000.0):""));','fxLive.setText("EXNESS • "+fxState+(fxStreamLastMs>0?" • STREAM":"")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):""));')
a=a.replace('if(market.equals("FOREX"))return "EXNESS • "+fxState+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.1fs",fxQuoteAgeMs/1000.0):"");','if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");')
ACT.write_text(a,encoding='utf-8')

# Android dependency + version
gr=GR.read_text(encoding='utf-8')
gr=gr.replace("versionCode 9","versionCode 10").replace("versionName '3.3.0'","versionName '3.4.0'")
if 'com.squareup.okhttp3:okhttp' not in gr:
    gr += "\ndependencies {\n    implementation 'com.squareup.okhttp3:okhttp:4.12.0'\n}\n"
GR.write_text(gr,encoding='utf-8')

# ApiClient gets WebSocket helper
api=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java'
s=api.read_text(encoding='utf-8')
if 'okhttp3.WebSocket' not in s:
    s=s.replace('import java.nio.charset.StandardCharsets;','import java.nio.charset.StandardCharsets;\n\nimport okhttp3.OkHttpClient;\nimport okhttp3.Request;\nimport okhttp3.WebSocket;\nimport okhttp3.WebSocketListener;\nimport java.util.concurrent.TimeUnit;')
    s=s.replace('    private ApiClient() {}','    private static final OkHttpClient LIVE_CLIENT = new OkHttpClient.Builder().pingInterval(10, TimeUnit.SECONDS).retryOnConnectionFailure(true).build();\n\n    private ApiClient() {}\n\n    public static WebSocket connectForexStream(WebSocketListener listener) {\n        String ws = BASE_URL.replace("https://","wss://").replace("http://","ws://") + "/v3/forex/stream";\n        Request r = new Request.Builder().url(ws).header("Cache-Control","no-cache").build();\n        return LIVE_CLIENT.newWebSocket(r, listener);\n    }')
    s=s.replace('SignalHub-Android/3.2.0-low-latency','SignalHub-Android/3.4.0-realtime')
api.write_text(s,encoding='utf-8')

# monitor labels/version only
m=MON.read_text(encoding='utf-8').replace('SignalHub V3.2 • LIVE MONITOR','SignalHub V3.4 • LIVE MONITOR')
MON.write_text(m,encoding='utf-8')

print('patched V3.4 realtime + order-state UI')
