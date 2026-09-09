from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
API=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
GRADLE=Path('signalhub-android/app/build.gradle')


def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

w=WORKER.read_text()
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.11.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.12.0';")
w=w.replace("versionCode: 17,\n  versionName: '3.11.0',\n  title: 'SignalHub 3.11.0',","versionCode: 18,\n  versionName: '3.12.0',\n  title: 'SignalHub 3.12.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.11.0',","artifactName: 'SignalHub-Android-v3.12.0',")
w=w.replace("    'V3.11 Atomic Quality Book reserves every active slot transactionally inside one Durable Object so concurrent scans cannot overbook the portfolio.',","    'V3.12 fixes Crypto LIMIT/STOP lifecycle gaps: active crypto orders are now evaluated server-side by a Durable Object alarm without depending on the app or /crypto/tickers polling.',\n    'V3.12 pins every Crypto signal to its creation exchange and only that exchange may trigger its Entry/SL/TP lifecycle, preventing cross-exchange false or missed fills.',\n    'V3.12 adds always-on dual-market coverage: MT5 realtime packets atomically claim an empty FOREX/CRYPTO market and launch an immediate structure-qualified refill in the background.',\n    'V3.11 Atomic Quality Book reserves every active slot transactionally inside one Durable Object so concurrent scans cannot overbook the portfolio.',")
old_policy="portfolioPolicy:{maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC'}"
new_policy="portfolioPolicy:{maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,minActivePerMarket:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'ALWAYS_ON_DUAL_MARKET',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S'}"
if old_policy not in w: raise SystemExit('market judgment policy pattern missing')
w=w.replace(old_policy,new_policy,1)
old_port="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC'});"
new_port="const PORTFOLIO_POLICY=Object.freeze({maxActiveTotal:6,maxActivePerMarket:4,maxActivePerStyle:3,maxNewPerScan:2,maxForexPerCurrency:2,minActivePerMarket:1,oneActivePerSymbolAcrossStyles:true,reservation:'DURABLE_OBJECT_ATOMIC',coverageMode:'ALWAYS_ON_DUAL_MARKET',cryptoPendingMonitor:'DURABLE_OBJECT_ALARM_1S'});"
if old_port not in w: raise SystemExit('portfolio policy pattern missing')
w=w.replace(old_port,new_port,1)

# Provider-key quote routing: a crypto signal must trigger only from the exchange that created it.
w=w.replace("    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);}","    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);const provider=String(q?.exchange||q?.provider||'').toUpperCase();if(provider)by.set(`${provider}:${sym}`,q);}",1)
w=w.replace("      const q=by.get(canonical(s.symbol));if(!q)continue;","      const sym=canonical(s.symbol),authority=String(s.executionPriceAuthority||s.provider||s.exchange||'').toUpperCase();\n      const q=String(market).toUpperCase()==='CRYPTO'&&authority?by.get(`${authority}:${sym}`):by.get(sym);if(!q)continue;",1)

# Add Durable Object portfolio coverage, crypto alarm monitor and provider-pinned lifecycle.
needle="  broadcast(obj){const msg=JSON.stringify(obj);for(const ws of [...this.clients]){try{ws.send(msg);}catch{this.clients.delete(ws);}}}\n  async registerSignal(payload){"
helpers=r'''  broadcast(obj){const msg=JSON.stringify(obj);for(const ws of [...this.clients]){try{ws.send(msg);}catch{this.clients.delete(ws);}}}
  activeRows(reg){return Object.values(reg||{}).filter(x=>x&&(x.status==='PENDING'||x.status==='OPEN'));}
  portfolioFrom(reg){
    const active=this.activeRows(reg),counts={FOREX:0,CRYPTO:0},styles={SCALP:0,SWING:0};
    for(const s of active){const m=String(s.market||'').toUpperCase(),st=String(s.style||'').toUpperCase();if(m in counts)counts[m]++;if(st in styles)styles[st]++;}
    return {activeTotal:active.length,counts,styles,uniqueSymbols:new Set(active.map(x=>`${String(x.market||'').toUpperCase()}:${canonical(x.symbol)}`)).size,policy:PORTFOLIO_POLICY};
  }
  async portfolioSnapshot(){return this.portfolioFrom(await this.registry());}
  async ensureCryptoMonitor(delayMs=25){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(!active.length){try{await this.state.storage.deleteAlarm();}catch{}return {ok:true,running:false,activeCrypto:0};}
    const target=Date.now()+Math.max(25,Number(delayMs)||25),old=await this.state.storage.getAlarm();
    if(old===null||Number(old)>target+250)await this.state.storage.setAlarm(target);
    return {ok:true,running:true,activeCrypto:active.length,nextAlarmMs:target};
  }
  async claimCoverage(){
    const now=Date.now();let out={claimed:[],portfolio:null};
    await this.state.storage.transaction(async txn=>{
      const reg=(await txn.get('signalRegistry'))||{},portfolio=this.portfolioFrom(reg),locks=(await txn.get('coverageLocks'))||{},claimed=[];
      for(const market of ['FOREX','CRYPTO']){
        const lock=locks[market],stale=lock&&now-Number(lock.claimedAt||0)>30000;
        if(stale)delete locks[market];
        if(Number(portfolio.counts?.[market]||0)<PORTFOLIO_POLICY.minActivePerMarket&&!locks[market]){locks[market]={claimedAt:now};claimed.push(market);}
      }
      await txn.put('coverageLocks',locks);out={claimed,portfolio};
    });
    return out;
  }
  async releaseCoverage(payload){
    const market=String(payload?.market||'').toUpperCase();if(!['FOREX','CRYPTO'].includes(market))return {ok:false,error:'BAD_MARKET'};
    await this.state.storage.transaction(async txn=>{const locks=(await txn.get('coverageLocks'))||{};delete locks[market];await txn.put('coverageLocks',locks);});return {ok:true,market};
  }
  async cryptoMonitorCycle(){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    const previous=(await this.state.storage.get('cryptoMonitorStatus'))||{},cycle=Number(previous.cycle||0)+1,at=nowIso();
    if(!active.length){const status={ok:true,running:false,cycle,activeCrypto:0,receivedAt:at};await this.state.storage.put('cryptoMonitorStatus',status);return status;}
    const providers=[...new Set(active.map(x=>String(x.executionPriceAuthority||x.provider||x.exchange||'BYBIT').toUpperCase()))],events=[],errors=[];let quotes=0;
    for(const provider of providers){
      try{const snap=await cryptoSnapshotForProvider(this.env,provider);if(snap.live===false||!snap.rows?.length){errors.push(`${provider}:NO_LIVE_ROWS`);continue;}quotes+=snap.rows.length;events.push(...await this.evaluate('CRYPTO',snap.rows,snap.receivedAt||at));}
      catch(e){errors.push(`${provider}:${String(e?.message||e)}`);}
    }
    const status={ok:errors.length<providers.length,running:true,cycle,activeCrypto:active.length,providers,quotes,events:events.length,errors,receivedAt:at};
    await this.state.storage.put('cryptoMonitorStatus',status);this.broadcast({type:'crypto_monitor',...status});return status;
  }
  async alarm(){
    try{await this.cryptoMonitorCycle();}catch(e){await this.state.storage.put('cryptoMonitorStatus',{ok:false,running:true,error:String(e?.message||e),receivedAt:nowIso()});}
    const reg=await this.registry(),still=this.activeRows(reg).some(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(still)await this.state.storage.setAlarm(Date.now()+1000);else try{await this.state.storage.deleteAlarm();}catch{}
  }
  async registerSignal(payload){'''
if needle not in w: raise SystemExit('DO helper insertion pattern missing')
w=w.replace(needle,helpers,1)

old_reg_tail="    this.signalRegistry=result.reg||this.signalRegistry;delete result.reg;return result;\n  }\n  async unregisterSignal"
new_reg_tail="    this.signalRegistry=result.reg||this.signalRegistry;delete result.reg;\n    if(result.accepted&&(s.status==='PENDING'||s.status==='OPEN')&&String(s.market||'').toUpperCase()==='CRYPTO')try{await this.ensureCryptoMonitor(25);}catch{}\n    return result;\n  }\n  async unregisterSignal"
if old_reg_tail not in w: raise SystemExit('register tail pattern missing')
w=w.replace(old_reg_tail,new_reg_tail,1)

# Extend DO internal routes and return coverage claims on every MT5 price event.
w=w.replace("    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/evaluate')", "    if(req.method==='POST'&&url.pathname==='/unregister-signal'){const p=await req.json();return new Response(JSON.stringify(await this.unregisterSignal(p)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/kick-crypto-monitor'){return new Response(JSON.stringify(await this.ensureCryptoMonitor(25)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='GET'&&url.pathname==='/crypto-monitor-status'){const status=(await this.state.storage.get('cryptoMonitorStatus'))||{ok:true,running:false,cycle:0};return new Response(JSON.stringify(status),{headers:{'content-type':'application/json'}});}\n    if(req.method==='GET'&&url.pathname==='/portfolio-snapshot'){return new Response(JSON.stringify(await this.portfolioSnapshot()),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/release-coverage'){const p=await req.json();return new Response(JSON.stringify(await this.releaseCoverage(p)),{headers:{'content-type':'application/json'}});}\n    if(req.method==='POST'&&url.pathname==='/evaluate')",1)
old_prices="      const packet=await req.json();await this.state.storage.put('quotes',packet);this.broadcast({type:'quotes',...packet});const events=await this.evaluate('FOREX',packet.quotes||[],packet.receivedAt);return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt,events:events.length}),{headers:{'content-type':'application/json'}});"
new_prices="      const packet=await req.json();await this.state.storage.put('quotes',packet);this.broadcast({type:'quotes',...packet});const events=await this.evaluate('FOREX',packet.quotes||[],packet.receivedAt),coverage=await this.claimCoverage();return new Response(JSON.stringify({ok:true,accepted:Number(packet.count||0),receivedAt:packet.receivedAt,events:events.length,coverageClaims:coverage.claimed,portfolio:coverage.portfolio}),{headers:{'content-type':'application/json'}});"
if old_prices not in w: raise SystemExit('DO prices pattern missing')
w=w.replace(old_prices,new_prices,1)

# Pin crypto signal execution authority to the provider used to create it.
old_crypto_src="source:t.source,exchange:t.exchange,provider:t.exchange,marketRegime:regime"
new_crypto_src="source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,marketRegime:regime"
if old_crypto_src not in w: raise SystemExit('crypto source pattern missing')
w=w.replace(old_crypto_src,new_crypto_src,1)

# Provider-specific snapshots for server-side crypto lifecycle monitoring.
load_end="  throw new Error('CRYPTO_ALL_PROVIDERS_UNAVAILABLE:'+errors.join('|'));\n}\nasync function cryptoTickers(url,env){"
provider_helper=r'''  throw new Error('CRYPTO_ALL_PROVIDERS_UNAVAILABLE:'+errors.join('|'));
}
async function cryptoSnapshotForProvider(env,provider){
  const p=String(provider||'BYBIT').toUpperCase();
  try{
    const snap=p==='OKX'?await okxTickers():p==='BINANCE'?await binanceTickers():await bybitTickers();
    return {...snap,provider:p,live:true};
  }catch(e){return {rows:[],provider:p,live:false,receivedAt:nowIso(),error:String(e?.message||e)};}
}
async function cryptoTickers(url,env){'''
if load_end not in w: raise SystemExit('crypto provider helper pattern missing')
w=w.replace(load_end,provider_helper,1)

# Real-time portfolio/coverage helpers. MT5's existing 500 ms price stream acts as the always-on refill heartbeat for BOTH markets.
mt5_stub_end="function mt5LiveStub(env){\n  if(!env?.MT5_LIVE)return null;\n  return env.MT5_LIVE.get(env.MT5_LIVE.idFromName('primary'));\n}\n\nasync function syncRealtimeSignal"
coverage_helpers=r'''function mt5LiveStub(env){
  if(!env?.MT5_LIVE)return null;
  return env.MT5_LIVE.get(env.MT5_LIVE.idFromName('primary'));
}
async function realtimePortfolioSnapshot(env){
  const stub=mt5LiveStub(env);if(!stub)return {activeTotal:0,counts:{FOREX:0,CRYPTO:0},styles:{SCALP:0,SWING:0}};
  try{const r=await stub.fetch('https://mt5-live/portfolio-snapshot');if(r.ok)return await r.json();}catch{}return {activeTotal:0,counts:{FOREX:0,CRYPTO:0},styles:{SCALP:0,SWING:0}};
}
async function releaseCoverageClaim(env,market){const stub=mt5LiveStub(env);if(!stub)return;try{await stub.fetch('https://mt5-live/release-coverage',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({market})});}catch{}}
async function kickCryptoServerMonitor(env){const stub=mt5LiveStub(env);if(!stub)return {ok:false,running:false};try{const r=await stub.fetch('https://mt5-live/kick-crypto-monitor',{method:'POST'});return r.ok?await r.json():{ok:false,running:false};}catch(e){return {ok:false,running:false,error:String(e?.message||e)};}}
async function cryptoServerMonitorStatus(env){const stub=mt5LiveStub(env);if(!stub)return {ok:false,running:false};try{const r=await stub.fetch('https://mt5-live/crypto-monitor-status');return r.ok?await r.json():{ok:false,running:false};}catch(e){return {ok:false,running:false,error:String(e?.message||e)};}}
async function refillMarketCoverage(env,market){
  const m=String(market||'').toUpperCase();let success=false;
  try{
    let p=await realtimePortfolioSnapshot(env);if(Number(p.counts?.[m]||0)>=PORTFOLIO_POLICY.minActivePerMarket){success=true;return;}
    if(m==='FOREX'){
      await scanForexScalp(env).catch(()=>{});p=await realtimePortfolioSnapshot(env);if(Number(p.counts?.FOREX||0)<PORTFOLIO_POLICY.minActivePerMarket)await scanForexSwing(env).catch(()=>{});
    }else if(m==='CRYPTO'){
      await scanCrypto(env,'SCALP').catch(()=>{});p=await realtimePortfolioSnapshot(env);if(Number(p.counts?.CRYPTO||0)<PORTFOLIO_POLICY.minActivePerMarket)await scanCrypto(env,'SWING').catch(()=>{});await kickCryptoServerMonitor(env);
    }
    p=await realtimePortfolioSnapshot(env);success=Number(p.counts?.[m]||0)>=PORTFOLIO_POLICY.minActivePerMarket;
  }finally{await releaseCoverageClaim(env,m);}
  return success;
}

async function syncRealtimeSignal'''
if mt5_stub_end not in w: raise SystemExit('coverage helper insertion pattern missing')
w=w.replace(mt5_stub_end,coverage_helpers,1)

# Expand crypto discovery only when that market is empty, while keeping hard structure checks.
old_rank="  const snap=await loadCryptoSnapshot(env),all=snap.rows;\n  const ranked=all.filter(x=>Number(x.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,style==='SCALP'?12:10);"
new_rank="  const snap=await loadCryptoSnapshot(env),all=snap.rows,portfolio=await realtimePortfolioSnapshot(env),marketEmpty=Number(portfolio.counts?.CRYPTO||0)<PORTFOLIO_POLICY.minActivePerMarket;\n  const rankedLimit=marketEmpty?(style==='SCALP'?16:14):(style==='SCALP'?12:10);\n  const ranked=all.filter(x=>Number(x.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,rankedLimit);"
if old_rank not in w: raise SystemExit('crypto rank pattern missing')
w=w.replace(old_rank,new_rank,1)

# MT5 bridge returns immediately; expensive refill scans run in ctx.waitUntil and never block quote ingestion.
w=w.replace("async function mt5Prices(req, env) {","async function mt5Prices(req, env, ctx) {",1)
old_stub_return="    const r=await stub.fetch('https://mt5-live/prices',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(packet)});\n    if(r.ok)return json({ok:true,accepted:quotes.length,receivedAt,transport:'DURABLE_OBJECT_REALTIME'});"
new_stub_return="    const r=await stub.fetch('https://mt5-live/prices',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(packet)});\n    if(r.ok){let state={};try{state=await r.json();}catch{}for(const market of state.coverageClaims||[])if(ctx?.waitUntil)ctx.waitUntil(Promise.resolve(refillMarketCoverage(env,market)).catch(()=>{}));return json({ok:true,accepted:quotes.length,receivedAt,transport:'DURABLE_OBJECT_REALTIME',coverageClaims:state.coverageClaims||[]});}"
if old_stub_return not in w: raise SystemExit('mt5 ctx return pattern missing')
w=w.replace(old_stub_return,new_stub_return,1)

# Public diagnostics/health endpoints and status visibility.
w=w.replace("async function v3Status(env){\n  const snap=await readMt5Realtime(env),mt5=snap?.heartbeat||null;\n  return json({ok:true,version:V3_VERSION", "async function v3Status(env){\n  const snap=await readMt5Realtime(env),mt5=snap?.heartbeat||null,portfolio=await realtimePortfolioSnapshot(env),cryptoMonitor=await cryptoServerMonitorStatus(env);\n  return json({ok:true,version:V3_VERSION",1)
w=w.replace("decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:","portfolio,cryptoMonitor,decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:",1)
w=w.replace("if(url.pathname==='/v3/mt5/prices'&&req.method==='POST')return mt5Prices(req,env);","if(url.pathname==='/v3/mt5/prices'&&req.method==='POST')return mt5Prices(req,env,ctx);",1)
w=w.replace("    if(url.pathname==='/v3/crypto/tickers'&&req.method==='GET')return cryptoTickers(url,env);","    if(url.pathname==='/v3/crypto/tickers'&&req.method==='GET')return cryptoTickers(url,env);\n    if(url.pathname==='/v3/crypto/monitor'&&req.method==='GET'){const kick=url.searchParams.get('kick')==='1'?await kickCryptoServerMonitor(env):null;return json({ok:true,version:V3_VERSION,status:await cryptoServerMonitorStatus(env),kick,portfolio:await realtimePortfolioSnapshot(env)});}\n    if(url.pathname==='/v3/portfolio'&&req.method==='GET')return json({ok:true,version:V3_VERSION,portfolio:await realtimePortfolioSnapshot(env),policy:PORTFOLIO_POLICY});",1)

# Scheduled scan remains a recovery layer and also kicks server-side monitoring; entry logic has no time gate.
w=w.replace("ctx.waitUntil((async()=>{await scanForexScalp(env).catch(()=>{});await sleep(100);await scanForexSwing(env).catch(()=>{});await sleep(100);await scanCrypto(env,'SCALP').catch(()=>{});await sleep(100);await scanCrypto(env,'SWING').catch(()=>{});})());","ctx.waitUntil((async()=>{await scanForexScalp(env).catch(()=>{});await sleep(100);await scanForexSwing(env).catch(()=>{});await sleep(100);await scanCrypto(env,'SCALP').catch(()=>{});await sleep(100);await scanCrypto(env,'SWING').catch(()=>{});await kickCryptoServerMonitor(env).catch(()=>{});})());",1)

# New signal IDs make the generation visible and retire previous-generation feed entries cleanly.
w=w.replace("id=`V311-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`","id=`V312-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`",1)
w=w.replace("REPLACED_BY_V310_DISCIPLINED_BOOK","REPLACED_BY_V312_ALWAYS_ON_DUAL_MARKET")
w=w.replace("V310_ACTIVE_BOOK_RESET","V312_ACTIVE_BOOK_RESET")

WORKER.write_text(w)

# Android: backend is now the only lifecycle authority. Never infer a crypto fill locally from a possibly different exchange quote.
a=ACT.read_text()
a=a.replace('APP_VERSION="3.11.0"','APP_VERSION="3.12.0"')
a=a.replace('SCALP ≠ SWING • STRUCTURE • ATOMIC QUALITY BOOK • REALTIME • V3.11','SCALP ≠ SWING • ALWAYS-ON DUAL MARKET • REALTIME • V3.12')
a=a.replace('LIVE  •  LIMIT  •  STOP  •  QUALITY GATE','LIVE  •  LIMIT  •  STOP  •  STRUCTURE ASSESSMENT')
a=a.replace('private boolean isDisplayLive(JSONObject s,double px){if("OPEN".equalsIgnoreCase(s.optString("status","")))return true;return "CRYPTO".equalsIgnoreCase(s.optString("market",""))&&pendingTriggered(s,px);}','private boolean isDisplayLive(JSONObject s,double px){return "OPEN".equalsIgnoreCase(s.optString("status",""));}')
a=a.replace('private String lifecycleVi(JSONObject s){double px=priceFor(s,s.optDouble("entry",0));if(pendingTriggered(s,px))return "ĐÃ KHỚP • LIVE";String x=', 'private String lifecycleVi(JSONObject s){String x=')
old_price='private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol",""),m=s.optString("market","FOREX");if(m.equals("CRYPTO")){JSONObject q=cryptoPrices.get(sym);return q==null?fallback:q.optDouble("lastPrice",fallback);}Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}'
new_price='private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol",""),m=s.optString("market","FOREX");if(m.equals("CRYPTO")){String authority=s.optString("executionPriceAuthority",s.optString("provider","")).toUpperCase(Locale.US);if(!authority.isEmpty()&&!authority.equalsIgnoreCase(cryptoProvider))return s.optDouble("lastPrice",fallback);JSONObject q=cryptoPrices.get(sym);return q==null?fallback:q.optDouble("lastPrice",fallback);}Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}'
if old_price not in a: raise SystemExit('android priceFor pattern missing')
a=a.replace(old_price,new_price,1)
a=a.replace('ui.addView(line("Entry Routing","MARKET / LIMIT / STOP tự động",TEXT));','ui.addView(line("Entry Routing","MARKET / LIMIT / STOP tự động",TEXT));ui.addView(line("Crypto Trigger","Server realtime monitor • app-independent",GREEN));ui.addView(line("Market Coverage","FOREX + CRYPTO luôn được refill khi trống",CYAN));')
ACT.write_text(a)

api=API.read_text().replace('SignalHub-Android/3.11.0-atomic-quality-book','SignalHub-Android/3.12.0-always-on-dual-market')
API.write_text(api)

mon=MON.read_text().replace('private static final long LOOP_MS=2000L;','private static final long LOOP_MS=1000L;')
MON.write_text(mon)

g=GRADLE.read_text().replace('versionCode 17','versionCode 18').replace("versionName '3.11.0'","versionName '3.12.0'")
GRADLE.write_text(g)
print('patched SignalHub V3.12 always-on crypto lifecycle + dual-market coverage')
