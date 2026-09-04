const CAPITAL_KEY='bybit:capital:intelligence:v1';
const CONTROL_KEY='bybit:auto:v1:controller';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const normalize=s=>String(s||'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const symbolKey=s=>normalize(s)==='BTCUSDT'?'bybit:btc:hyperscale:v2:state':`bybit:asset:${normalize(s)}:state`;

async function get(env,key,d={}){try{return await env.TRADING_STATE?.get(key,{type:'json'})??d}catch{return d}}
async function put(env,key,v){if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(v));}

export async function getCapitalIntelligenceState(env){return get(env,CAPITAL_KEY,{});}

export async function mirrorCapitalState(env,balance={}){
  if(!env.TRADING_STATE)return {ok:false,reason:'TRADING_STATE_KV_REQUIRED',tradingExecuted:false};
  const st=balance?.state||{},snap=balance?.snapshot||{},equity=num(snap.equityUsd||st.lastEquityUsd),wallet=num(snap.walletBalanceUsd||st.lastWalletBalanceUsd),available=num(snap.availableUsd||st.lastAvailableUsd),capacity=Math.max(0,Math.min(equity,num(st.continuousCapitalUsd)||equity)),high=Math.max(equity,num(st.highWaterUsd)||equity),now=new Date().toISOString();
  if(!(equity>0&&wallet>0&&capacity>0))return {ok:false,reason:'CAPITAL_MIRROR_INVALID_ACCOUNT',tradingExecuted:false,equity,wallet,capacity};
  const ctl=await get(env,CONTROL_KEY,{}),active=Array.isArray(ctl.activePositions)?ctl.activePositions:[],symbols=[...new Set(['BTCUSDT',...active.map(x=>normalize(x?.symbol)).filter(Boolean)])];
  const capitalIntelligence={authority:st.continuousScaleAuthority||'CAPITAL_INTELLIGENCE_V4',stateVersion:num(st.capitalStateVersion)||4,highWaterUsd:high,protectedEquityUsd:num(st.protectedEquityUsd),lastExternalCashFlow:st.lastExternalCashFlow||null,recognition:st.capitalRecognition||null,transactionLogPages:num(st.transactionLogPages),transactionLogRows:num(st.transactionLogRows),mirroredAt:now};
  const nextCtl={...ctl,equityUsd:equity,continuousCapacityCapitalUsd:capacity,walletBalanceUsd:wallet,availableUsd:available,capitalIntelligence,balanceReconcileReason:balance?.reason||null,externalCashFlowUsd:num(balance?.netExternalCashFlowUsd),capitalStateMirroredAt:now,capitalMirrorTradingExecuted:false};
  await put(env,CONTROL_KEY,nextCtl);
  const migrated=[];
  for(const symbol of symbols){
    const key=symbolKey(symbol),old=await get(env,key,{});
    if(!old||!Object.keys(old).length)continue;
    const next={...old,highWaterUsd:high,lastEquityUsd:equity,lastWalletBalanceUsd:wallet,lastAvailableUsd:available,lastContinuousCapitalUsd:capacity,globalCapitalHighWaterUsd:high,capitalAuthority:'GLOBAL_CAPITAL_INTELLIGENCE_V4',capitalMirroredAt:now};
    await put(env,key,next);migrated.push(symbol);
  }
  return {ok:true,tradingExecuted:false,controllerMirrored:true,symbolMetadataMirrored:migrated,equityUsd:equity,walletBalanceUsd:wallet,availableUsd:available,continuousCapitalUsd:capacity,highWaterUsd:high,capitalIntelligence};
}

export const BYBIT_CAPITAL_STATE_VERSION='BYBIT_CAPITAL_STATE_MIRROR_V1_READONLY_EXECUTION';
