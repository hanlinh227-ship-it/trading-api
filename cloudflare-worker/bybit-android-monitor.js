import {bybitExecutionMode} from './bybit-auto-config.js';
import {BYBIT_AUTO_VERSION,BYBIT_RUNTIME_CONTRACT} from './bybit-runtime-contract.js';
import {bybitV5} from './bybit-v5-client.js';
import {getMultiAssetControllerState} from './bybit-multi-asset-controller.js';
import {buildBybitDynamicUniverse} from './bybit-dynamic-universe.js';
import {BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,BYBIT_ANDROID_MONITOR_ROUTES,BYBIT_ANDROID_MONITOR_CAPABILITIES} from './bybit-android-monitor-contract.js';

const TOKEN_KEY='bybit:android:monitor:token:v1';
const enc=new TextEncoder();
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const on=v=>String(v||'').toLowerCase()==='true';
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const nowIso=()=>new Date().toISOString();
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'}});
const perfNow=()=>typeof performance!=='undefined'&&performance.now?performance.now():Date.now();

let bridgeCache={at:0,value:null,promise:null};
let universeCache={at:0,value:null,promise:null};

async function sha256Hex(s){const d=await crypto.subtle.digest('SHA-256',enc.encode(String(s||'')));return [...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,'0')).join('');}
function secureEq(a,b){a=String(a||'');b=String(b||'');if(!a||!b||a.length!==b.length)return false;let x=0;for(let i=0;i<a.length;i++)x|=a.charCodeAt(i)^b.charCodeAt(i);return x===0;}
function bearer(req){const raw=String(req.headers.get('authorization')||'');return raw.replace(/^Bearer\s+/i,'').trim()||String(req.headers.get('x-monitor-token')||'').trim();}
async function kvGet(env,key,d=null){try{return await env.TRADING_STATE?.get(key,{type:'json'})??d}catch{return d;}}
async function monitorAuth(req,env){
  const token=bearer(req);if(!token)return {ok:false,reason:'MONITOR_TOKEN_REQUIRED'};
  const configured=String(env.BYBIT_MONITOR_TOKEN||'').trim();if(configured&&secureEq(token,configured))return {ok:true,source:'STATIC_MONITOR_TOKEN',scope:'TELEMETRY_READ_ONLY'};
  const state=await kvGet(env,TOKEN_KEY,null);if(!state?.sha256)return {ok:false,reason:'MONITOR_NOT_PAIRED'};
  const hash=await sha256Hex(token);return secureEq(hash,state.sha256)?{ok:true,source:'PAIRED_MONITOR_TOKEN',scope:'TELEMETRY_READ_ONLY',deviceName:state.deviceName||null}:{ok:false,reason:'MONITOR_TOKEN_INVALID'};
}
function actionBootstrapAuth(req,env){const expected=String(env.GPT_5AI_ACTION_KEY||'').trim(),got=String(req.headers.get('x-action-key')||'').trim();return !!expected&&secureEq(got,expected);}
function randomToken(){const a=new Uint8Array(32);crypto.getRandomValues(a);let s='';for(const b of a)s+=String.fromCharCode(b);return 'bam1_'+btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');}
async function pairMonitor(req,env){
  if(!actionBootstrapAuth(req,env))return json({ok:false,error:'PAIR_REQUIRES_ACTION_KEY',readOnly:true},401);
  if(!env.TRADING_STATE)return json({ok:false,error:'TRADING_STATE_KV_REQUIRED'},503);
  let body={};try{body=await req.json()}catch{}
  const deviceName=String(body?.deviceName||'Android Monitor').replace(/[\r\n\t]/g,' ').slice(0,80),token=randomToken(),sha256=await sha256Hex(token),at=Date.now();
  await env.TRADING_STATE.put(TOKEN_KEY,JSON.stringify({sha256,createdAt:at,rotatedAt:at,deviceName,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,scope:'TELEMETRY_READ_ONLY'}));
  return json({ok:true,readOnly:true,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,token,tokenType:'Bearer',scope:'TELEMETRY_READ_ONLY',deviceName,createdAt:new Date(at).toISOString(),warning:'TOKEN_IS_SHOWN_ONCE_STORE_IN_ANDROID_KEYSTORE'});
}

async function cached(key,ttl,loader){
  const cache=key==='bridge'?bridgeCache:universeCache,now=Date.now();
  if(cache.value&&now-cache.at<ttl)return cache.value;
  if(cache.promise)return cache.promise;
  cache.promise=(async()=>{try{const v=await loader();cache.value=v;cache.at=Date.now();return v}finally{cache.promise=null}})();return cache.promise;
}
async function bridgeFetch(env,path){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')throw new Error('BYBIT_VPS_BRIDGE_BINDING_MISSING');
  const t=perfNow(),r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789'+path,{method:'GET',headers:{accept:'application/json'}})),latencyMs=Math.max(0,perfNow()-t),body=await r.json().catch(()=>null);
  if(!r.ok||!body?.ok){const e=new Error(body?.error||body?.reason||`VPS_BRIDGE_HTTP_${r.status}`);e.status=r.status;throw e;}
  return {...body,workerToVpsLatencyMs:Number(latencyMs.toFixed(2))};
}
const loadBridgeHealth=env=>cached('bridge',1000,()=>bridgeFetch(env,'/health'));
async function loadUniverse(env){
  return cached('universe',5000,async()=>{
    const api=bybitV5(env),publicApi={
      tickers:()=>api.public('/v5/market/tickers',{category:'linear'}),
      instruments:(cursor='')=>api.public('/v5/market/instruments-info',{category:'linear',limit:1000,cursor})
    };
    return buildBybitDynamicUniverse(env,publicApi);
  });
}
function closedSummary(rows=[],hours=24,now=Date.now()){
  const start=now-hours*3600000,x=rows.filter(r=>num(r.updatedTime||r.createdTime)>=start),pnls=x.map(r=>num(r.closedPnl)),wins=pnls.filter(v=>v>0),losses=pnls.filter(v=>v<0),flat=pnls.filter(v=>v===0),net=pnls.reduce((a,b)=>a+b,0),grossWin=wins.reduce((a,b)=>a+b,0),grossLoss=Math.abs(losses.reduce((a,b)=>a+b,0));
  return {windowHours:hours,closedRecords:pnls.length,wins:wins.length,losses:losses.length,flat:flat.length,winRatePct:pnls.length?Number((wins.length/pnls.length*100).toFixed(2)):0,realizedPnl:Number(net.toFixed(6)),grossProfit:Number(grossWin.toFixed(6)),grossLoss:Number(grossLoss.toFixed(6)),profitFactor:grossLoss>0?Number((grossWin/grossLoss).toFixed(3)):(grossWin>0?99:0),expectancy:pnls.length?Number((net/pnls.length).toFixed(6)):0,lastClosedAt:x.length?new Date(Math.max(...x.map(r=>num(r.updatedTime||r.createdTime)))).toISOString():null};
}
function governorWindow(g={},hours=24){
  const last=num(g.lastClosedAt);return {windowHours:hours,closedRecords:num(g.trades),wins:num(g.wins),losses:num(g.losses),flat:Math.max(0,num(g.trades)-num(g.wins)-num(g.losses)),winRatePct:Number((num(g.winRate)*100).toFixed(2)),realizedPnl:Number(num(g.netPnl).toFixed(6)),grossProfit:Number((num(g.avgWin)*num(g.wins)).toFixed(6)),grossLoss:Number((num(g.avgLoss)*num(g.losses)).toFixed(6)),profitFactor:num(g.profitFactor),expectancy:num(g.expectancy),lastClosedAt:last>0?new Date(last).toISOString():null};
}
function positionRow(x={}){
  const size=Math.abs(num(x.size)),entry=num(x.avgPrice),mark=num(x.markPrice),leverage=num(x.leverage),pnl=num(x.unrealisedPnl),positionValue=Math.abs(num(x.positionValue))||(mark>0?size*mark:entry>0?size*entry:0),positionIM=Math.abs(num(x.positionIM)),marginBasis=positionIM>0?positionIM:(leverage>0?positionValue/leverage:0),roe=marginBasis>0?pnl/marginBasis*100:null;
  return {symbol:String(x.symbol||''),side:String(x.side||''),size,entryPrice:entry,markPrice:mark,unrealizedPnl:pnl,roePct:roe===null?null:Number(roe.toFixed(3)),roeSource:positionIM>0?'UNREALIZED_PNL_OVER_POSITION_IM':'UNREALIZED_PNL_OVER_NOTIONAL_DIV_LEVERAGE',leverage,tp:num(x.takeProfit),sl:num(x.stopLoss),liqPrice:num(x.liqPrice),positionValue,positionMargin:marginBasis,positionIdx:num(x.positionIdx)};
}
function scannerRow(r={}){return {symbol:r.symbol,classification:r.classification,reason:r.reason||null,eligible:r.eligible===true,lastPrice:num(r.last),score:Number(num(r.score).toFixed(4)),spreadBps:Number(num(r.spreadBps).toFixed(3)),turnover24h:num(r.turnover),change24hPct:Number((num(r.change)*100).toFixed(3)),openInterestValue:num(r.oiValue),maxLeverage:num(r.maxLeverage)||null,style:r.style||'BALANCED',ageDays:r.ageDays===null?null:Number(num(r.ageDays).toFixed(2)),promotionPotential:r.promotion?.potential??null};}
function scannerSnapshot(u={}){
  const rows=Array.isArray(u.ranked)?u.ranked:[],confirmed=rows.filter(x=>x.eligible).map(scannerRow),noTrade=rows.filter(x=>x.classification==='DO_NOT_TRADE').map(scannerRow),watching=rows.filter(x=>!x.eligible&&x.classification!=='DO_NOT_TRADE').map(scannerRow);
  return {authority:u.authority||null,source:'BYBIT_PUBLIC_MARKET_PLUS_BOT_UNIVERSE_RULES',generatedAt:u.at?new Date(u.at).toISOString():null,total:rows.length,confirmedTradeableCount:confirmed.length,watchingCount:watching.length,noTradeCount:noTrade.length,confirmedTradeable:confirmed,watching,noTrade};
}
function positionsSummary(rows=[]){
  let longCount=0,shortCount=0,longNotional=0,shortNotional=0,pnl=0;for(const p of rows){const n=Math.abs(num(p.positionValue));pnl+=num(p.unrealizedPnl);if(p.side==='Buy'){longCount++;longNotional+=n}else if(p.side==='Sell'){shortCount++;shortNotional+=n}}
  return {openCount:rows.length,longCount,shortCount,longNotional:Number(longNotional.toFixed(6)),shortNotional:Number(shortNotional.toFixed(6)),netDirectionalNotional:Number((longNotional-shortNotional).toFixed(6)),totalUnrealizedPnl:Number(pnl.toFixed(6))};
}
function botState(env,controller={},bridge={}){
  const mode=bybitExecutionMode(env),enabled=on(env.BYBIT_AUTO_ENABLED),liveAck=on(env.BYBIT_BTC_LIVE_ACK),ws=bridge.wsTelemetry||{},accountReady=num(controller.equityUsd)>0||num(controller.walletBalanceUsd)>0,ready=enabled&&(mode!=='LIVE'||liveAck)&&accountReady&&bridge.ok===true&&num(ws.connectedCount)>0,status=!enabled?'DISABLED':mode==='LIVE'&&ready?'LIVE_RUNNING':mode==='PAPER'&&ready?'PAPER_RUNNING':'DEGRADED';
  return {status,ready,mode,enabled,liveAck,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,runtimeRevision:String(env.RUNTIME_REVISION||'UNKNOWN'),decisionAuthority:controller.decisionAuthority||'VPS_WS_MARKET_STATE_CHANGE',entrySelectionAuthority:controller.entrySelectionAuthority||null,lastCycleAt:controller.lastCycleAt||null,lastCycleReason:controller.lastCycleReason||null,lastCycleExecuted:!!controller.lastCycleExecuted,lastEventSymbol:controller.lastEventSymbol||null,monitorAffectsTrading:false};
}
export async function buildBybitAndroidSnapshot(env){
  const started=perfNow(),generatedMs=Date.now();
  const [bridge,controller,universe]=await Promise.all([loadBridgeHealth(env),getMultiAssetControllerState(env),loadUniverse(env)]);
  const positions=(Array.isArray(controller?.activePositions)?controller.activePositions:[]).filter(x=>num(x.size)>0).map(positionRow),summary=positionsSummary(positions),pg=controller?.performanceGovernor?.summary||{},p24=governorWindow(pg.h24||{},24),p72=governorWindow(pg.h72||{},72),scanner=scannerSnapshot(universe),ws=bridge.wsTelemetry||{},snapshotBuildMs=Math.max(0,perfNow()-started),wsAge=num(ws.p95DataAgeMs||ws.maxDataAgeMs),scannerAge=universe?.at?Math.max(0,generatedMs-num(universe.at)):null,cycleMs=Date.parse(String(controller?.lastCycleAt||'')),accountAge=Number.isFinite(cycleMs)?Math.max(0,generatedMs-cycleMs):null;
  const account={equity:num(controller.equityUsd),balance:num(controller.walletBalanceUsd),availableBalance:num(controller.availableUsd),unrealizedPnl:summary.totalUnrealizedPnl,realizedPnl:p24.realizedPnl,realizedPnlWindowHours:24,realizedPnl72h:p72.realizedPnl,source:'BOT_CONTROLLER_RECONCILED_ACCOUNT_STATE'};
  const bot=botState(env,controller,bridge),accountReady=account.equity>0||account.balance>0;
  return {ok:true,readOnly:true,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,generatedAt:new Date(generatedMs).toISOString(),generatedAtMs:generatedMs,bot,connection:{bybitAuthenticated:accountReady?true:null,authenticationEvidence:accountReady?'LAST_SUCCESSFUL_CONTROLLER_ACCOUNT_RECONCILIATION':null,privateTelemetrySource:'NO_PRIVATE_BYBIT_CALLS_FROM_MONITOR',workerToVpsHealthLatencyMs:num(bridge.workerToVpsLatencyMs),bybitWs:{status:ws.healthy?'HEALTHY':num(ws.connectedCount)>0?'DEGRADED':'DOWN',healthy:ws.healthy===true,connectedCount:num(ws.connectedCount),readyCount:num(ws.readyCount),freshCount:num(ws.freshCount),symbolCount:num(bridge.symbols?.length),maxWsSymbols:num(bridge.maxWsSymbols),eventSymbolCount:num(bridge.eventSymbols?.length),eventSymbols:bridge.eventSymbols||[],staleSymbols:ws.staleSymbols||[],source:'VPS_BYBIT_PUBLIC_WS'},latency:{snapshotBuildMs:Number(snapshotBuildMs.toFixed(2)),workerToVpsHealthMs:num(bridge.workerToVpsLatencyMs)},dataAge:{wsP50Ms:ws.p50DataAgeMs??null,wsP95Ms:ws.p95DataAgeMs??null,wsMaxMs:ws.maxDataAgeMs??null,accountMs:accountAge,scannerMs:scannerAge,overallMs:Math.max(wsAge||0,accountAge||0,scannerAge||0)}},account,performance:{source:'BOT_PERFORMANCE_GOVERNOR_BYBIT_CLOSED_PNL',winRatePct:p24.winRatePct,realizedPnl:p24.realizedPnl,h24:p24,h72:p72},positionsSummary:summary,positions,scanner,controller:{marketDirectionBreadth:controller.marketDirectionBreadth||null,performanceGovernor:controller.performanceGovernor?.summary||null,bestUniverseSymbol:controller.bestUniverseSymbol||null,candidateRanking:controller.objectiveCandidateRanking||[],candidateDecisions:controller.candidateDecisions||[]},security:{androidScope:'TELEMETRY_READ_ONLY',bybitApiSecretReturned:false,bybitApiKeyReturned:false,bybitApiSecretAccessedByMonitor:false,privateTelemetrySigningAuthority:'NONE_MONITOR_USES_RECONCILED_CONTROLLER_STATE',tradingEndpointsExposedByMonitor:false}};
}


function bootstrap(){return {ok:true,readOnly:true,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,routes:BYBIT_ANDROID_MONITOR_ROUTES,capabilities:BYBIT_ANDROID_MONITOR_CAPABILITIES,auth:{type:'Bearer',header:'Authorization: Bearer <monitor-token>',pairingRequires:'x-action-key',queryStringTokenAllowed:false},websocketProtocol:{serverMessages:['snapshot','pong','telemetry_error','error'],clientMessages:['subscribe','sync','ping'],defaultIntervalMs:1500,minIntervalMs:1000,maxIntervalMs:10000,executionCommands:false},checkedAt:nowIso()};}
async function authHealth(env){const paired=await kvGet(env,TOKEN_KEY,null);return {ok:true,readOnly:true,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,configured:Boolean(String(env.BYBIT_MONITOR_TOKEN||'').trim()||paired?.sha256),paired:!!paired?.sha256,deviceName:paired?.deviceName||null,scope:'TELEMETRY_READ_ONLY',checkedAt:nowIso()};}
function wsResponse(client){return new Response(null,{status:101,webSocket:client,headers:{'cache-control':'no-store'}});}
async function openWebSocket(req,env,ctx){
  const auth=await monitorAuth(req,env);if(!auth.ok)return json({ok:false,error:auth.reason,readOnly:true},401);
  if(String(req.headers.get('upgrade')||'').toLowerCase()!=='websocket')return json({ok:false,error:'WEBSOCKET_UPGRADE_REQUIRED'},426);
  const pair=new WebSocketPair(),[client,server]=Object.values(pair);server.accept();let closed=false,timer=null,inflight=false,intervalMs=1500,seq=0;
  const stop=()=>{closed=true;if(timer){clearTimeout(timer);timer=null}};
  const send=async(force=false)=>{if(closed||inflight&&!force)return;inflight=true;try{const data=await buildBybitAndroidSnapshot(env);if(!closed)server.send(JSON.stringify({type:'snapshot',seq:++seq,sentAt:Date.now(),data}))}catch(e){if(!closed)server.send(JSON.stringify({type:'telemetry_error',seq:++seq,sentAt:Date.now(),error:String(e?.message||e).slice(0,240)}))}finally{inflight=false}};
  const schedule=()=>{if(closed)return;timer=setTimeout(async()=>{await send();schedule()},intervalMs)};
  server.addEventListener('message',event=>{let m={};try{m=JSON.parse(String(event.data||'{}'))}catch{m={type:String(event.data||'')}}const type=String(m.type||'');if(type==='ping'){server.send(JSON.stringify({type:'pong',clientAt:m.clientAt??null,serverAt:Date.now()}));return}if(type==='sync'){void send(true);return}if(type==='subscribe'){intervalMs=Math.round(clamp(num(m.intervalMs)||1500,1000,10000));server.send(JSON.stringify({type:'subscribed',intervalMs,readOnly:true}));return}server.send(JSON.stringify({type:'error',error:'READ_ONLY_PROTOCOL_MESSAGE_NOT_ALLOWED',allowed:['subscribe','sync','ping']}));});
  server.addEventListener('close',stop);server.addEventListener('error',stop);void send(true).then(schedule);return wsResponse(client);
}

export async function handleBybitAndroidMonitor(req,env,ctx){
  const u=new URL(req.url),p=u.pathname;if(!p.startsWith('/bybit/monitor/'))return null;
  if(p===BYBIT_ANDROID_MONITOR_ROUTES.bootstrap&&req.method==='GET')return json(bootstrap());
  if(p===BYBIT_ANDROID_MONITOR_ROUTES.authHealth&&req.method==='GET')return json(await authHealth(env));
  if(p===BYBIT_ANDROID_MONITOR_ROUTES.pair&&req.method==='POST')return pairMonitor(req,env);
  if(p===BYBIT_ANDROID_MONITOR_ROUTES.snapshot&&req.method==='GET'){const a=await monitorAuth(req,env);if(!a.ok)return json({ok:false,error:a.reason,readOnly:true},401);try{return json(await buildBybitAndroidSnapshot(env))}catch(e){return json({ok:false,readOnly:true,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,error:'MONITOR_SNAPSHOT_FAILED',detail:String(e?.message||e).slice(0,240)},502)}}
  if(p===BYBIT_ANDROID_MONITOR_ROUTES.websocket&&req.method==='GET')return openWebSocket(req,env,ctx);
  return json({ok:false,error:'ANDROID_MONITOR_ROUTE_NOT_FOUND',readOnly:true},404);
}
