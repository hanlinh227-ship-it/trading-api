from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
GRADLE=Path('signalhub-android/app/build.gradle')
WRANGLER=Path('signalhub-worker/wrangler.jsonc')


def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

w=WORKER.read_text()
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.7.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.8.0';")
w=w.replace("versionCode: 13,\n  versionName: '3.7.0',\n  title: 'SignalHub 3.7.0',","versionCode: 14,\n  versionName: '3.8.0',\n  title: 'SignalHub 3.8.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.7.0',","artifactName: 'SignalHub-Android-v3.8.0',")
w=w.replace("    'V3.7 Structure-Liquidity Engine: entries, stops and targets are derived from live structure, liquidity/rejection and volatility context.',","    'V3.8 separates SCALP microstructure execution from SWING higher-timeframe execution and tracks pending triggers continuously.',\n    'LIMIT/STOP activation is event-driven from live prices; Forex uses MT5 Ask for BUY triggers and Bid for SELL triggers.',\n    'V3.7 Structure-Liquidity Engine retained: entries, stops and targets are derived from live structure, liquidity/rejection and volatility context.',")
w=w.replace("  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION'","  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION',\n  styleSeparation:'SCALP_MICROSTRUCTURE_VS_SWING_HTF_STRUCTURE',\n  pendingActivation:'PRICE_TOUCH_EVENT_DRIVEN_NO_COOLDOWN'")

style_policy=r'''
const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'sweep/reclaim, micro pullback, momentum continuation, breakout trigger',stopFocus:'nearest validated microstructure invalidation + volatility/spread buffer',targetFocus:'local liquidity then 15m/1h structure',holdModel:'short-horizon active management'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'H1 pullback/reclaim, HTF continuation, H1 breakout confirmation',stopFocus:'H1/H4 invalidation + wider volatility buffer',targetFocus:'H4/D1 liquidity and structural expansion',holdModel:'multi-session structure hold'})
});
'''
w=w.replace("function validSignalStructure(signal){",style_policy+"\nfunction validSignalStructure(signal){")
w=w.replace("  signal.style=String(style||signal.style||'SCALP').toUpperCase();\n  delete signal.score;", "  signal.style=String(style||signal.style||'SCALP').toUpperCase();\n  signal.styleProfile=STYLE_EXECUTION_POLICY[signal.style]||STYLE_EXECUTION_POLICY.SCALP;\n  delete signal.score;")

new_do=r'''export class MT5LiveState {
  constructor(state, env) {
    this.state=state;this.env=env;this.clients=new Set();this.signalRegistry=null;
  }
  async registry(){if(this.signalRegistry===null)this.signalRegistry=(await this.state.storage.get('signalRegistry'))||{};return this.signalRegistry;}
  async persistRegistry(){await this.state.storage.put('signalRegistry',this.signalRegistry||{});}
  broadcast(obj){const msg=JSON.stringify(obj);for(const ws of [...this.clients]){try{ws.send(msg);}catch{this.clients.delete(ws);}}}
  async registerSignal(payload){
    const s=payload?.signal||payload,id=String(s?.id||s?.signalId||'');if(!id)return {ok:false,error:'NO_SIGNAL_ID'};
    const reg=await this.registry();
    if(s.status==='PENDING'||s.status==='OPEN')reg[id]={...s,kvKey:String(payload?.kvKey||`v31:signal:${s.market}:${s.style}:${id}`)};else delete reg[id];
    await this.persistRegistry();return {ok:true,id,status:s.status};
  }
  async unregisterSignal(payload){const id=String(payload?.id||payload?.signalId||'');if(!id)return {ok:false};const reg=await this.registry();delete reg[id];await this.persistRegistry();return {ok:true,id};}
  async evaluate(market,rows,receivedAt){
    const reg=await this.registry(),by=new Map();
    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);}
    const changed=[],at=receivedAt||nowIso();let dirty=false;
    for(const [id,s] of Object.entries(reg)){
      if(String(s.market||'').toUpperCase()!==String(market||'').toUpperCase())continue;
      if(s.status!=='PENDING'&&s.status!=='OPEN'){delete reg[id];dirty=true;continue;}
      const q=by.get(canonical(s.symbol));if(!q)continue;
      const dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
      let entryPx,exitPx;
      if(String(market).toUpperCase()==='FOREX'){
        const bid=Number(q.bid||q.mid||0),ask=Number(q.ask||q.mid||0);entryPx=dir>0?ask:bid;exitPx=dir>0?bid:ask;
      }else{const last=Number(q.lastPrice||q.last||q.mid||0);entryPx=last;exitPx=last;}
      if(!(entryPx>0&&exitPx>0))continue;
      const entry=Number(s.entry),sl=Number(s.sl),tp=Number(s.tp3||s.tp);let mutated=false,eventType='';
      if(s.status==='PENDING'){
        const type=String(s.orderType||'').toUpperCase();
        const trigger=type==='LIMIT'?(dir>0?entryPx<=entry:entryPx>=entry):type==='STOP'?(dir>0?entryPx>=entry:entryPx<=entry):false;
        if(trigger){s.status='OPEN';s.lifecycle='ACTIVE';s.entryState='LIVE';s.triggeredAt=at;s.triggerPrice=entryPx;s.actualEntry=s.actualEntry||entry;s.executionStatus='PRICE_TRIGGERED_AWAITING_BROKER_CONFIRM';eventType='TRIGGERED';mutated=true;}
      }
      if(s.status==='OPEN'){
        const hitTp=dir>0?exitPx>=tp:exitPx<=tp,hitSl=dir>0?exitPx<=sl:exitPx>=sl;
        if(hitTp||hitSl){s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=hitTp?tp:sl;s.resultR=hitTp?Number(s.targetRR||0):-1;s.resolution='REALTIME_EVENT_TRACKER';eventType=s.outcome;mutated=true;delete reg[id];dirty=true;}
      }
      if(mutated){
        s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`);const clean={...s};delete clean.kvKey;
        if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});if(clean.status==='CLOSED')await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);}
        if(clean.status!=='CLOSED')reg[id]={...clean,kvKey};dirty=true;changed.push({type:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,at});this.broadcast({type:'signal_event',event:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,receivedAt:at});
      }
    }
    if(dirty)await this.persistRegistry();return changed;
  }
  async fetch(req) {
    const url=new URL(req.url);
    if(req.headers.get('Upgrade')==='websocket'){
      const pair=new WebSocketPair(),client=pair[0],server=pair[1];server.accept();this.clients.add(server);const drop=()=>this.clients.delete(server);server.addEventListener('close',drop);server.addEventListener('error',drop);
      try{const quotes=await this.state.storage.get('quotes'),heartbeat=await this.state.storage.get('heartbeat');if(quotes)server.send(JSON.stringify({type:'quotes',...quotes,heartbeat:heartbeat||null}));}catch{}
      return new Response(null,{status:101,webSocket:client});
    }
    if(req.method==='POST'&&url.pathname==='/register-signal'){const p=await req.json();return new Response(JSON.stringify(await this.registerSignal(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/evaluate'){const p=await req.json(),events=await this.evaluate(p.market,p.rows||[],p.receivedAt);return new Response(JSON.stringify({ok:true,events}),{headers:{'content-type':'application/json'}});}
    if(req.method==='POST'&&url.pathname==='/prices'){
      const packet=await req.json();await this.state.storage.put('quotes',packet);this.broadcast({type:'quotes',...packet});const events=await this.evaluate('FOREX',packet.quotes||[],packet.receivedAt);return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt,events:events.length}),{headers:{'content-type':'application/json'}});
    }
    if(req.method==='POST'&&url.pathname==='/heartbeat'){const heartbeat=await req.json();await this.state.storage.put('heartbeat',heartbeat);this.broadcast({type:'heartbeat',heartbeat});return new Response(JSON.stringify({ok:true,receivedAt:heartbeat.receivedAt}),{headers:{'content-type':'application/json'}});}
    if(url.pathname==='/snapshot'){const [quotes,heartbeat]=await Promise.all([this.state.storage.get('quotes'),this.state.storage.get('heartbeat')]);return new Response(JSON.stringify({ok:!!quotes,quotes:quotes||null,heartbeat:heartbeat||null}),{headers:{'content-type':'application/json','cache-control':'no-store'}});}
    return new Response('not found',{status:404});
  }
}'''
w=sub1(w,r"export class MT5LiveState \{.*?\n\}\nfunction mt5LiveStub",new_do+"\nfunction mt5LiveStub",'replace realtime DO')

sync_helper=r'''
async function syncRealtimeSignal(env,s,kvKey){
  const stub=mt5LiveStub(env);if(!stub||!s)return;
  try{
    if(s.status==='PENDING'||s.status==='OPEN')await stub.fetch('https://mt5-live/register-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({signal:s,kvKey})});
    else await stub.fetch('https://mt5-live/unregister-signal',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:s.id||s.signalId})});
  }catch{}
}
'''
w=w.replace("async function readMt5Realtime(env){",sync_helper+"\nasync function readMt5Realtime(env){")

old_write="async function writeV31Signal(env,s){const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});if(s.status==='PENDING'||s.status==='OPEN')await env.SIGNALS_KV.put(activePointer(s.market,s.style,s.symbol),s.id,{expirationTtl:SIGNAL_TTL});else await env.SIGNALS_KV.delete(activePointer(s.market,s.style,s.symbol));}"
new_write="async function writeV31Signal(env,s){const key=v31Prefix(s.market,s.style)+s.id;await env.SIGNALS_KV.put(key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});if(s.status==='PENDING'||s.status==='OPEN')await env.SIGNALS_KV.put(activePointer(s.market,s.style,s.symbol),s.id,{expirationTtl:SIGNAL_TTL});else await env.SIGNALS_KV.delete(activePointer(s.market,s.style,s.symbol));await syncRealtimeSignal(env,s,key);}"
if old_write not in w: raise SystemExit('writeV31Signal exact text not found')
w=w.replace(old_write,new_write)

# Broker events must keep the realtime registry synchronized too.
w=w.replace("  s.lastCheckedAt=receivedAt;await env.SIGNALS_KV.put(found.key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});\n  return {patched:true,status:s.status,outcome:s.outcome||null};", "  s.lastCheckedAt=receivedAt;await env.SIGNALS_KV.put(found.key,JSON.stringify(s),{expirationTtl:SIGNAL_TTL});await syncRealtimeSignal(env,s,found.key);\n  return {patched:true,status:s.status,outcome:s.outcome||null};")

# Resolve V3x market/style ids to the real partition key for broker fill events.
w=w.replace("async function loadSignalById(kv,id){\n  for(const key of [`signal:${id}`,`v31:signal:${id}`]){", "async function loadSignalById(kv,id){\n  const parts=String(id||'').split('-'),partition=(parts.length>3&&/^V3\\d+$/.test(parts[0]))?`v31:signal:${parts[1]}:${parts[2]}:${id}`:null;\n  for(const key of [`signal:${id}`,`v31:signal:${id}`,partition].filter(Boolean)){")

# Every crypto live snapshot evaluates pending/active orders in the same realtime registry.
old_crypto="async function cryptoTickers(url,env){\n  const snap=await loadCryptoSnapshot(env),limit=Math.min(1000,Math.max(1,Number(url.searchParams.get('limit')||1000)));\n  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:snap.live!==false,staleFallback:snap.staleFallback===true,ageMs:snap.ageMs??0,count:snap.rows.length,tickers:snap.rows.slice(0,limit),exchangeTime:snap.exchangeTime,receivedAt:snap.receivedAt,providerErrors:snap.errors||[],note:'Bybit is preferred. Any fallback exchange is explicitly labeled and is never presented as Bybit live.'});\n}"
new_crypto="async function cryptoTickers(url,env){\n  const snap=await loadCryptoSnapshot(env),limit=Math.min(1000,Math.max(1,Number(url.searchParams.get('limit')||1000)));\n  if(snap.live!==false){const stub=mt5LiveStub(env);if(stub){try{await stub.fetch('https://mt5-live/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market:'CRYPTO',rows:snap.rows,receivedAt:snap.receivedAt})});}catch{}}}\n  return json({ok:true,version:V3_VERSION,market:'CRYPTO_USDT_PERP',provider:snap.provider,live:snap.live!==false,staleFallback:snap.staleFallback===true,ageMs:snap.ageMs??0,count:snap.rows.length,tickers:snap.rows.slice(0,limit),exchangeTime:snap.exchangeTime,receivedAt:snap.receivedAt,providerErrors:snap.errors||[],note:'Bybit is preferred. Live snapshots also drive pending-order activation; fallback exchange is explicitly labeled.'});\n}"
if old_crypto not in w: raise SystemExit('cryptoTickers exact text not found')
w=w.replace(old_crypto,new_crypto)

# Make SCALP and SWING risk/target geometry explicitly different while keeping structure first.
w=w.replace("  const spread=Number(t.spreadBps??0),atr1=a.atr,spreadPx=Math.max(0,px*spread/10000),entryBuffer=Math.max(atr1*(style==='SCALP'?.055:.075),spreadPx*1.8);", "  const spread=Number(t.spreadBps??0),atr1=a.atr,spreadPx=Math.max(0,px*spread/10000),profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,entryBuffer=Math.max(atr1*(style==='SCALP'?.045:.085),spreadPx*(style==='SCALP'?1.8:2.2));")
w=w.replace("  const stopBuffer=Math.max(atr1*(style==='SCALP'?.12:.17),spreadPx*2.6);", "  const stopBuffer=Math.max(atr1*(style==='SCALP'?.11:.22),spreadPx*(style==='SCALP'?2.6:3.2));")
w=w.replace("    else anchor=Math.min(a.recentLow,a.ema50-.08*atr1);", "    else anchor=style==='SCALP'?Math.min(a.recentLow,a.ema50-.08*atr1):Math.min(a.recentLow,b.recentLow,b.ema50-.10*b.atr);")
w=w.replace("    else anchor=Math.max(a.recentHigh,a.ema50+.08*atr1);", "    else anchor=style==='SCALP'?Math.max(a.recentHigh,a.ema50+.08*atr1):Math.max(a.recentHigh,b.recentHigh,b.ema50+.10*b.atr);")
w=w.replace("entry+risk*(style==='SCALP'?2.25:2.65)","entry+risk*(style==='SCALP'?2.10:2.85)")
w=w.replace("entry-risk*(style==='SCALP'?2.25:2.65)","entry-risk*(style==='SCALP'?2.10:2.85)")
w=w.replace("invalidationLevel:Number(anchor.toPrecision(10)),executionCaution", "invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution")

# Forex: wider HTF invalidation for SWING, faster local invalidation for SCALP.
w=w.replace("  const entryBuffer=atr*(style==='SCALP'?.055:.075),strongImpulse", "  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,entryBuffer=atr*(style==='SCALP'?.045:.09),strongImpulse")
w=w.replace("  const stopBuffer=atr*(style==='SCALP'?.13:.18);let anchor;", "  const stopBuffer=atr*(style==='SCALP'?.12:.24);let anchor;")
w=w.replace("if(style==='SWING'&&lowB<entry&&entry-lowB<2.8*atr)anchor=Math.min(anchor,lowB);", "if(style==='SWING'&&lowB<entry)anchor=Math.min(anchor,lowB,r.ema50B-.12*r.atrB);")
w=w.replace("if(style==='SWING'&&highB>entry&&highB-entry<2.8*atr)anchor=Math.max(anchor,highB);", "if(style==='SWING'&&highB>entry)anchor=Math.max(anchor,highB,r.ema50B+.12*r.atrB);")
w=w.replace("entry+risk*(style==='SCALP'?2.20:2.60)","entry+risk*(style==='SCALP'?2.05:2.90)")
w=w.replace("entry-risk*(style==='SCALP'?2.20:2.60)","entry-risk*(style==='SCALP'?2.05:2.90)")
w=w.replace("invalidationLevel:anchor,technicalAtIssue", "invalidationLevel:anchor,styleExecutionModel:profile.name,executionFrames:profile.frames,technicalAtIssue")

w=w.replace("id=`V36-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`","id=`V38-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`")
WORKER.write_text(w)

j=ACT.read_text()
j=j.replace('private static final String APP_VERSION="3.7.0";','private static final String APP_VERSION="3.8.0";')
j=j.replace('STRUCTURE • LIQUIDITY • REALTIME • V3.7','SCALP ≠ SWING • STRUCTURE • REALTIME • V3.8')
j=j.replace('V3.5 STRICT • chỉ phát setup vượt quality gate; WR vẫn chỉ tính TP/SL đã đóng.','V3.8 MARKET JUDGMENT • không score gate • LIMIT/STOP kích hoạt theo giá live.')

# Forex signal events from the Durable Object update lifecycle immediately instead of waiting for page refresh.
old_consume='private void consumeForexStream(String text){\n        try{JSONObject p=new JSONObject(text),packet=p;String type=p.optString("type","");if(type.equals("heartbeat")){return;}JSONArray a=packet.optJSONArray("quotes");'
new_consume='private void consumeForexStream(String text){\n        try{JSONObject p=new JSONObject(text),packet=p;String type=p.optString("type","");if(type.equals("heartbeat")){return;}if(type.equals("signal_event")){JSONObject sig=p.optJSONObject("signal");if(sig!=null)applyRealtimeSignal(sig);return;}JSONArray a=packet.optJSONArray("quotes");'
if old_consume not in j: raise SystemExit('consumeForexStream anchor not found')
j=j.replace(old_consume,new_consume)

apply_method=r'''
    private void applyRealtimeSignal(JSONObject sig){
        try{
            String market=sig.optString("market","FOREX").toUpperCase(Locale.US),st=sig.optString("style","SCALP").toUpperCase(Locale.US),key=market+":"+st,id=sig.optString("signalId",sig.optString("id",""));
            JSONArray old=signalCache.get(key),next=new JSONArray();boolean found=false,active="PENDING".equalsIgnoreCase(sig.optString("status",""))||"OPEN".equalsIgnoreCase(sig.optString("status",""));
            if(old!=null)for(int i=0;i<old.length();i++){JSONObject x=old.optJSONObject(i);if(x==null)continue;String xid=x.optString("signalId",x.optString("id",""));if(xid.equals(id)){found=true;if(active)next.put(sig);}else next.put(x);}
            if(!found&&active)next.put(sig);signalCache.put(key,next);
            if(selectedSignal!=null){String sid=selectedSignal.optString("signalId",selectedSignal.optString("id",""));if(sid.equals(id))selectedSignal=sig;}
            main.post(()->{if(screen.equals("SIGNALS")){if(detail&&selectedSignal!=null)renderDetail(selectedSignal,false);else renderSignals(false);}else if(screen.equals("HOME"))renderHome(false);});
        }catch(Throwable ignored){}
    }
'''
j=j.replace("    private void refreshForexLive(){",apply_method+"\n    private void refreshForexLive(){")

# Pending Forex only becomes LIVE from exact backend bid/ask trigger event; Crypto can promote on its live last price snapshot.
j=j.replace('private boolean isDisplayLive(JSONObject s,double px){return "OPEN".equalsIgnoreCase(s.optString("status",""))||pendingTriggered(s,px);}', 'private boolean isDisplayLive(JSONObject s,double px){if("OPEN".equalsIgnoreCase(s.optString("status","")))return true;return "CRYPTO".equalsIgnoreCase(s.optString("market",""))&&pendingTriggered(s,px);}')

# Display the execution model so SCALP/SWING difference is explicit.
j=j.replace('c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("ENTRY MODEL"', 'c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("STYLE MODEL",s.optString("styleExecutionModel",signalStyle.equals("SCALP")?"SCALP MICROSTRUCTURE":"SWING HTF STRUCTURE").replace(\'_\',\' \'),CYAN));c.addView(line("ENTRY MODEL"')
ACT.write_text(j)

m=MON.read_text()
m=m.replace('private static final long LOOP_MS=5000L;','private static final long LOOP_MS=2000L;')
m=m.replace('SignalHub V3.7 • LIVE MONITOR','SignalHub V3.8 • LIVE MONITOR')
# Background monitor requests crypto live snapshot so pending crypto orders are evaluated while the app is not foregrounded.
m=m.replace('    private void syncAll(){\n        int active=0,failed=0;', '    private void syncAll(){\n        try{ApiClient.getLive("/v3/crypto/tickers?limit=1000");}catch(Throwable ignored){}\n        int active=0,failed=0;')
MON.write_text(m)

g=GRADLE.read_text().replace('versionCode 13','versionCode 14').replace("versionName '3.7.0'","versionName '3.8.0'")
GRADLE.write_text(g)

wr=WRANGLER.read_text().replace('"crons": ["*/5 * * * *"]','"crons": ["* * * * *"]')
WRANGLER.write_text(wr)
print('patched SignalHub V3.8: explicit scalp/swing profiles + event-driven pending activation')
