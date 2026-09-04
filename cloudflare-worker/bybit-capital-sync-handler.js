import {reconcileBtcAccountBalance} from './bybit-btc-balance-reconciler.js';
import {mirrorCapitalState} from './bybit-capital-state.js';

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
function auth(req,env){const raw=String(req.headers.get('x-action-key')||req.headers.get('authorization')||'').replace(/^Bearer\s+/i,''),a=String(env.GPT_5AI_ACTION_KEY||''),b=String(env.V11_AI_BRIDGE_SECRET||env.BYBIT_VPS_BRIDGE_SECRET||'');return !!raw&&((a&&raw===a)||(b&&raw===b));}

export async function handleBybitCapitalSync(req,env){
  const u=new URL(req.url);if(u.pathname!=='/bybit/capital/sync')return null;
  if(req.method!=='GET')return json({ok:false,readOnlyExecution:true,tradingExecuted:false,error:'METHOD_NOT_ALLOWED'},405);
  if(!auth(req,env))return json({ok:false,readOnlyExecution:true,tradingExecuted:false,error:'UNAUTHORIZED'},401);
  try{
    const b=await reconcileBtcAccountBalance(env),st=b.state||{},snap=b.snapshot||{},mirror=await mirrorCapitalState(env,b);
    return json({ok:b.ok!==false&&mirror.ok!==false,readOnlyExecution:true,tradingExecuted:false,reason:b.reason||null,netExternalCashFlowUsd:Number(b.netExternalCashFlowUsd||0),account:{equityUsd:Number(snap.equityUsd||0),walletBalanceUsd:Number(snap.walletBalanceUsd||0),availableUsd:Number(snap.availableUsd||0)},capital:{stateVersion:Number(st.capitalStateVersion||0),continuousCapitalUsd:Number(st.continuousCapitalUsd||0),highWaterUsd:Number(st.highWaterUsd||0),protectedEquityUsd:Number(st.protectedEquityUsd||0),authority:st.continuousScaleAuthority||null,recognition:st.capitalRecognition||null,lastExternalCashFlow:st.lastExternalCashFlow||null,transactionLogPages:Number(st.transactionLogPages||0),transactionLogRows:Number(st.transactionLogRows||0)},mirror,guarantees:['NO_ORDER_SUBMISSION','NO_TP_SL_CHANGE','NO_LEVERAGE_CHANGE','NO_POSITION_CHANGE','KV_CAPITAL_METADATA_ONLY'],checkedAt:new Date().toISOString()});
  }catch(e){return json({ok:false,readOnlyExecution:true,tradingExecuted:false,reason:'CAPITAL_SYNC_FAILED',error:String(e?.message||e).slice(0,300)},502);}
}
