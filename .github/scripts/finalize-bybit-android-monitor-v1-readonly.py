from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

# Android monitor: consume reconciled controller/account state and public market data only.
p=ROOT/'cloudflare-worker/bybit-android-monitor.js'
s=p.read_text()
s=s.replace("const bridgeSecret=env=>String(env?.V11_AI_BRIDGE_SECRET||env?.BYBIT_VPS_BRIDGE_SECRET||'').trim();\n","")
s=s.replace("let privateCache={at:0,value:null,promise:null};\n","")
s=s.replace("  const cache=key==='private'?privateCache:key==='bridge'?bridgeCache:universeCache,now=Date.now();","  const cache=key==='bridge'?bridgeCache:universeCache,now=Date.now();")
old="""async function bridgeFetch(env,path,{authorized=false}={}){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')throw new Error('BYBIT_VPS_BRIDGE_BINDING_MISSING');
  const headers={'accept':'application/json'};if(authorized){const secret=bridgeSecret(env);if(!secret)throw new Error('BYBIT_VPS_BRIDGE_SECRET_MISSING');headers.authorization='Bearer '+secret;}
  const t=perfNow(),r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789'+path,{method:'GET',headers})),latencyMs=Math.max(0,perfNow()-t),body=await r.json().catch(()=>null);
  if(!r.ok||!body?.ok){const e=new Error(body?.error||body?.reason||`VPS_BRIDGE_HTTP_${r.status}`);e.status=r.status;throw e;}
  return {...body,workerToVpsLatencyMs:Number(latencyMs.toFixed(2))};
}
const loadBridgeHealth=env=>cached('bridge',1000,()=>bridgeFetch(env,'/health'));
const loadPrivateTelemetry=env=>cached('private',1000,()=>bridgeFetch(env,'/bybit/telemetry',{authorized:true}));
"""
new="""async function bridgeFetch(env,path){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')throw new Error('BYBIT_VPS_BRIDGE_BINDING_MISSING');
  const t=perfNow(),r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789'+path,{method:'GET',headers:{accept:'application/json'}})),latencyMs=Math.max(0,perfNow()-t),body=await r.json().catch(()=>null);
  if(!r.ok||!body?.ok){const e=new Error(body?.error||body?.reason||`VPS_BRIDGE_HTTP_${r.status}`);e.status=r.status;throw e;}
  return {...body,workerToVpsLatencyMs:Number(latencyMs.toFixed(2))};
}
const loadBridgeHealth=env=>cached('bridge',1000,()=>bridgeFetch(env,'/health'));
"""
if old not in s:raise SystemExit('MONITOR_BRIDGE_FETCH_PATTERN_MISSING')
s=s.replace(old,new,1)
marker="function positionRow(x={}){"
helper="""function governorWindow(g={},hours=24){
  const last=num(g.lastClosedAt);return {windowHours:hours,closedRecords:num(g.trades),wins:num(g.wins),losses:num(g.losses),flat:Math.max(0,num(g.trades)-num(g.wins)-num(g.losses)),winRatePct:Number((num(g.winRate)*100).toFixed(2)),realizedPnl:Number(num(g.netPnl).toFixed(6)),grossProfit:Number((num(g.avgWin)*num(g.wins)).toFixed(6)),grossLoss:Number((num(g.avgLoss)*num(g.losses)).toFixed(6)),profitFactor:num(g.profitFactor),expectancy:num(g.expectancy),lastClosedAt:last>0?new Date(last).toISOString():null};
}
"""
if marker not in s:raise SystemExit('POSITION_MARKER_MISSING')
s=s.replace(marker,helper+marker,1)
start=s.index("function botState(")
end=s.index("\n\nfunction bootstrap()",start)
replacement="""function botState(env,controller={},bridge={}){
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
"""
s=s[:start]+replacement+s[end:]
p.write_text(s)

# VPS bridge: keep only additive WS status/data-age telemetry; remove unused private telemetry signer.
p=ROOT/'bybit-live-bridge/bybit_live_bridge.py'
s=p.read_text()
s=s.replace("import hashlib, hmac, json, math, os, subprocess, threading, time, urllib.error, urllib.parse, urllib.request","import json, math, os, subprocess, threading, time, urllib.error, urllib.parse, urllib.request")
for line in [
"TELEMETRY_API_KEY=(os.environ.get('BYBIT_AUTO_API_KEY') or os.environ.get('HYRO_BYBIT_LIVE_API_KEY') or os.environ.get('HYRO_BYBIT_API_KEY') or '').strip()\n",
"TELEMETRY_API_SECRET=(os.environ.get('BYBIT_AUTO_API_SECRET') or os.environ.get('HYRO_BYBIT_LIVE_API_SECRET') or os.environ.get('HYRO_BYBIT_API_SECRET') or '').strip()\n",
"TELEMETRY_RECV_WINDOW=str(max(5000,min(20000,int(os.environ.get('BYBIT_RECV_WINDOW_MS','10000')))))\n"]:
    s=s.replace(line,'')
start=s.find("\ndef _bybit_readonly_get(")
end=s.find("\ndef ws_telemetry(",start)
if start<0 or end<0:raise SystemExit('BRIDGE_PRIVATE_TELEMETRY_BLOCK_MISSING')
s=s[:start]+s[end:]
route="""        if u.path=='/bybit/telemetry':
            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
            try:return self.sendj(200,readonly_telemetry())
            except Exception as e:return self.sendj(503,{'ok':False,'readOnly':True,'error':'BYBIT_TELEMETRY_FAILED','detail':str(e)[:240]})
"""
s=s.replace(route,'')
p.write_text(s)
print('BYBIT_ANDROID_MONITOR_V1_CREDENTIALLESS_FINALIZED')
