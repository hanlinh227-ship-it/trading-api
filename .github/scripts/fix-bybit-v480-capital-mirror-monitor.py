from pathlib import Path
R=Path(__file__).resolve().parents[2]

# Control plane: capital sync must immediately mirror account capital into controller/symbol metadata without trading.
p=R/'cloudflare-worker/bybit-control-plane.js';s=p.read_text()
old="import {reconcileBtcAccountBalance} from './bybit-btc-balance-reconciler.js';\n"
new=old+"import {mirrorCapitalState} from './bybit-capital-state.js';\n"
if "mirrorCapitalState" not in s:
    if old not in s: raise SystemExit('CONTROL_IMPORT_MARKER_MISSING')
    s=s.replace(old,new,1)
old_route="if(u.pathname==='/bybit/capital/sync'&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);try{const b=await reconcileBtcAccountBalance(env),st=b.state||{},snap=b.snapshot||{};return json({ok:b.ok!==false,readOnlyExecution:true,tradingExecuted:false,reason:b.reason||null,netExternalCashFlowUsd:Number(b.netExternalCashFlowUsd||0),account:{equityUsd:Number(snap.equityUsd||0),walletBalanceUsd:Number(snap.walletBalanceUsd||0),availableUsd:Number(snap.availableUsd||0)},capital:{stateVersion:Number(st.capitalStateVersion||0),continuousCapitalUsd:Number(st.continuousCapitalUsd||0),highWaterUsd:Number(st.highWaterUsd||0),protectedEquityUsd:Number(st.protectedEquityUsd||0),authority:st.continuousScaleAuthority||null,recognition:st.capitalRecognition||null,lastExternalCashFlow:st.lastExternalCashFlow||null,transactionLogPages:Number(st.transactionLogPages||0),transactionLogRows:Number(st.transactionLogRows||0)},checkedAt:new Date().toISOString()})}catch(e){return json({ok:false,readOnlyExecution:true,tradingExecuted:false,reason:'CAPITAL_SYNC_FAILED',error:String(e?.message||e)},502)}}"
new_route="if(u.pathname==='/bybit/capital/sync'&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);try{const b=await reconcileBtcAccountBalance(env),st=b.state||{},snap=b.snapshot||{},mirror=await mirrorCapitalState(env,b);return json({ok:b.ok!==false&&mirror.ok!==false,readOnlyExecution:true,tradingExecuted:false,reason:b.reason||null,netExternalCashFlowUsd:Number(b.netExternalCashFlowUsd||0),account:{equityUsd:Number(snap.equityUsd||0),walletBalanceUsd:Number(snap.walletBalanceUsd||0),availableUsd:Number(snap.availableUsd||0)},capital:{stateVersion:Number(st.capitalStateVersion||0),continuousCapitalUsd:Number(st.continuousCapitalUsd||0),highWaterUsd:Number(st.highWaterUsd||0),protectedEquityUsd:Number(st.protectedEquityUsd||0),authority:st.continuousScaleAuthority||null,recognition:st.capitalRecognition||null,lastExternalCashFlow:st.lastExternalCashFlow||null,transactionLogPages:Number(st.transactionLogPages||0),transactionLogRows:Number(st.transactionLogRows||0)},mirror,guarantees:['CAPITAL_SYNC_DOES_NOT_SUBMIT_ORDERS','CAPITAL_SYNC_DOES_NOT_CHANGE_TP_SL','CAPITAL_SYNC_DOES_NOT_CHANGE_LEVERAGE','CAPITAL_SYNC_ONLY_RECONCILES_ACCOUNT_AND_KV_METADATA'],checkedAt:new Date().toISOString()})}catch(e){return json({ok:false,readOnlyExecution:true,tradingExecuted:false,reason:'CAPITAL_SYNC_FAILED',error:String(e?.message||e)},502)}}"
if "CAPITAL_SYNC_ONLY_RECONCILES_ACCOUNT_AND_KV_METADATA" not in s:
    if old_route not in s: raise SystemExit('CONTROL_CAPITAL_ROUTE_MARKER_MISSING')
    s=s.replace(old_route,new_route,1)
p.write_text(s)

# Android monitor: account values use freshest dedicated capital state; positions remain WS mark-to-market.
p=R/'cloudflare-worker/bybit-android-monitor.js';s=p.read_text()
old="import {getMultiAssetControllerState} from './bybit-multi-asset-controller.js';\n"
new=old+"import {getCapitalIntelligenceState} from './bybit-capital-state.js';\n"
if "getCapitalIntelligenceState" not in s:
    if old not in s: raise SystemExit('MONITOR_IMPORT_MARKER_MISSING')
    s=s.replace(old,new,1)
old="const [bridge,controller,universe]=await Promise.all([loadBridgeHealth(env),getMultiAssetControllerState(env),loadUniverse(env)]);"
new="const [bridge,controller,universe,capitalState]=await Promise.all([loadBridgeHealth(env),getMultiAssetControllerState(env),loadUniverse(env),getCapitalIntelligenceState(env)]);"
if old in s:s=s.replace(old,new,1)
elif new not in s:raise SystemExit('MONITOR_PROMISE_MARKER_MISSING')
old="const realtimePnlDelta=summary.totalUnrealizedPnl-reconciledSummary.totalUnrealizedPnl,realtimeEquity=num(controller.equityUsd)>0?num(controller.equityUsd)+realtimePnlDelta:num(controller.equityUsd),account={equity:Number(realtimeEquity.toFixed(8)),balance:num(controller.walletBalanceUsd),availableBalance:num(controller.availableUsd),unrealizedPnl:summary.totalUnrealizedPnl,realizedPnl:p24.realizedPnl,realizedPnlWindowHours:24,realizedPnl72h:p72.realizedPnl,source:'BOT_CONTROLLER_PLUS_VPS_WS_MARK_TO_MARKET'};"
new="const realtimePnlDelta=summary.totalUnrealizedPnl-reconciledSummary.totalUnrealizedPnl,baseEquity=num(capitalState.lastEquityUsd)||num(controller.equityUsd),baseWallet=num(capitalState.lastWalletBalanceUsd)||num(controller.walletBalanceUsd),baseAvailable=num(capitalState.lastAvailableUsd)||num(controller.availableUsd),realtimeEquity=baseEquity>0?baseEquity+realtimePnlDelta:baseEquity,account={equity:Number(realtimeEquity.toFixed(8)),balance:baseWallet,availableBalance:baseAvailable,unrealizedPnl:summary.totalUnrealizedPnl,realizedPnl:p24.realizedPnl,realizedPnlWindowHours:24,realizedPnl72h:p72.realizedPnl,continuousCapitalUsd:num(capitalState.continuousCapitalUsd)||num(controller.continuousCapacityCapitalUsd),capitalHighWaterUsd:num(capitalState.highWaterUsd)||num(controller.capitalIntelligence?.highWaterUsd),source:'CAPITAL_INTELLIGENCE_PLUS_VPS_WS_MARK_TO_MARKET'};"
if old in s:s=s.replace(old,new,1)
elif "CAPITAL_INTELLIGENCE_PLUS_VPS_WS_MARK_TO_MARKET" not in s:raise SystemExit('MONITOR_ACCOUNT_MARKER_MISSING')
old="cycleMs=Date.parse(String(controller?.lastCycleAt||'')),accountAge=Number.isFinite(cycleMs)?Math.max(0,generatedMs-cycleMs):null;"
new="cycleMs=Date.parse(String(controller?.lastCycleAt||'')),capitalMs=Date.parse(String(capitalState?.lastBalanceObservedAt||'')),freshAccountMs=Number.isFinite(capitalMs)?capitalMs:cycleMs,accountAge=Number.isFinite(freshAccountMs)?Math.max(0,generatedMs-freshAccountMs):null;"
if old in s:s=s.replace(old,new,1)
elif "freshAccountMs" not in s:raise SystemExit('MONITOR_ACCOUNT_AGE_MARKER_MISSING')
old="positionsSummary:summary,positions,scanner,controller:{"
new="positionsSummary:summary,positions,scanner,capital:{stateVersion:num(capitalState.capitalStateVersion),continuousCapitalUsd:num(capitalState.continuousCapitalUsd),highWaterUsd:num(capitalState.highWaterUsd),protectedEquityUsd:num(capitalState.protectedEquityUsd),authority:capitalState.continuousScaleAuthority||null,recognition:capitalState.capitalRecognition||null,lastExternalCashFlow:capitalState.lastExternalCashFlow||null,lastObservedAt:capitalState.lastBalanceObservedAt||null},controller:{"
if old in s:s=s.replace(old,new,1)
elif "lastExternalCashFlow:capitalState.lastExternalCashFlow" not in s:raise SystemExit('MONITOR_CAPITAL_PAYLOAD_MARKER_MISSING')
p.write_text(s)
print('BYBIT_V480_CAPITAL_MIRROR_MONITOR_FIXED')
