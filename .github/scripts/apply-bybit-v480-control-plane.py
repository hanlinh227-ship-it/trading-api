from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'cloudflare-worker/bybit-control-plane.js';s=p.read_text()
old="import {bybitV5} from './bybit-v5-client.js';"
new=old+"\nimport {reconcileBtcAccountBalance} from './bybit-btc-balance-reconciler.js';"
if "reconcileBtcAccountBalance" not in s:s=s.replace(old,new,1)
needle="if(u.pathname==='/bybit/runtime/preflight'&&req.method==='GET')"
route="if(u.pathname==='/bybit/capital/sync'&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);try{const b=await reconcileBtcAccountBalance(env),st=b.state||{},snap=b.snapshot||{};return json({ok:b.ok!==false,readOnlyExecution:true,tradingExecuted:false,reason:b.reason||null,netExternalCashFlowUsd:Number(b.netExternalCashFlowUsd||0),account:{equityUsd:Number(snap.equityUsd||0),walletBalanceUsd:Number(snap.walletBalanceUsd||0),availableUsd:Number(snap.availableUsd||0)},capital:{stateVersion:Number(st.capitalStateVersion||0),continuousCapitalUsd:Number(st.continuousCapitalUsd||0),highWaterUsd:Number(st.highWaterUsd||0),protectedEquityUsd:Number(st.protectedEquityUsd||0),authority:st.continuousScaleAuthority||null,recognition:st.capitalRecognition||null,lastExternalCashFlow:st.lastExternalCashFlow||null,transactionLogPages:Number(st.transactionLogPages||0),transactionLogRows:Number(st.transactionLogRows||0)},checkedAt:new Date().toISOString()})}catch(e){return json({ok:false,readOnlyExecution:true,tradingExecuted:false,reason:'CAPITAL_SYNC_FAILED',error:String(e?.message||e)},502)}}"
if route not in s:
    if needle not in s:raise SystemExit('CONTROL_PLANE_INSERT_PATTERN_MISSING')
    s=s.replace(needle,route+needle,1)
p.write_text(s)
print('BYBIT_V480_CONTROL_PLANE_PATCHED')
